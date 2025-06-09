async def _parse_recipe_with_names(self, data):
        """Parse API response into Recipe object with component name lookups"""
        try:
            # Log the raw data structure for debugging
            logger.debug(f"Parsing recipe data: {json.dumps(data, indent=2)[:300]}...")
            
            # Extract basic recipe information
            name = data.get("name", "Unknown Recipe")
            trivial_level = data.get("trivial", None)
            skill_needed = data.get("skillneeded", 0)
            tradeskill_id = data.get("tradeskill", None)
            
            # Map tradeskill ID to name
            if tradeskill_id is not None:
                profession = self.TRADESKILL_NAMES.get(tradeskill_id, f"Unknown Skill ({tradeskill_id})")
                logger.debug(f"Mapped tradeskill ID {tradeskill_id} to {profession}")
            else:
                profession = "Unknown"
            
            # Parse tradeskill_entries for components and container
            components = []
            crafting_station = "Unknown"
            
            tradeskill_entries = data.get("tradeskill_entries", [])
            if isinstance(tradeskill_entries, list):
                for entry in tradeskill_entries:
                    if isinstance(entry, dict):
                        # Check if this is a crafting container
                        if entry.get("iscontainer", 0) == 1:
                            container_item_id = entry.get("item_id")
                            # Look up container name
                            container_data = await self.get_item_by_id(str(container_item_id))
                            if container_data and container_data.get("name"):
                                crafting_station = container_data.get("name")
                            else:
                                crafting_station = f"Container ID: {container_item_id}"
                            logger.debug(f"Found crafting container: {crafting_station}")
                        
                        # Check if this is a component (has componentcount > 0)
                        elif entry.get("componentcount", 0) > 0:
                            item_id = entry.get("item_id")
                            quantity = entry.get("componentcount", 1)
                            
                            # Look up component name
                            component_data = await self.get_item_by_id(str(item_id))
                            if component_data and component_data.get("name"):
                                component_name = component_data.get("name")
                            else:
                                component_name = f"Item ID: {item_id}"
                            
                            component = {
                                "name": component_name,
                                "quantity": quantity,
                                "item_id": item_id
                            }
                            components.append(component)
                            logger.debug(f"Found component: {quantity}x {component_name}")
            
            # Ensure numeric fields are properly typed
            try:
                skill_level = int(skill_needed) if skill_needed is not None else 0
            except (ValueError, TypeError):
                logger.warning(f"Invalid skill_needed value: {skill_needed}, defaulting to 0")
                skill_level = 0
                
            try:
                trivial_level = int(trivial_level) if trivial_level is not None else None
            except (ValueError, TypeError):
                logger.warning(f"Invalid trivial_level value: {trivial_level}, setting to None")
                trivial_level = None
            
            recipe = Recipe(
                name=str(name),
                skill_level=skill_level,
                profession=str(profession),
                crafting_station=str(crafting_station),
                components=components,
                success_rate=None,  # Not available in this API response format
                trivial_level=trivial_level
            )
            
            logger.debug(f"Successfully parsed recipe: {recipe.name} ({recipe.profession})")
            return recipe
            
        except Exception as e:
            logger.error(f"Error parsing recipe data: {e}")
            # Return a basic recipe with error information
            return Recipe(
                name="Error parsing recipe",
                skill_level=0,
                profession="Unknown",
                crafting_station="Unknown",
                components=[]
            )#!/usr/bin/env python3
"""
EverQuest Crafting Request Bot
A Discord bot that handles crafting item requests and displays recipes from eqdb.net
"""

import os
import logging
import asyncio
import aiohttp
import discord
from discord.ext import commands
from dataclasses import dataclass
from datetime import datetime
import json
import re
import signal
import sys

# Import typing - fix the Dict import issue
from typing import Optional, Dict, Any, List, Tuple, Union

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    logging.warning("python-dotenv not installed. Environment variables must be set manually.")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('eq_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class Recipe:
    """Data class for crafting recipe information"""
    name: str
    skill_level: int
    profession: str
    crafting_station: str
    components: List[Dict[str, Any]]
    success_rate: Optional[str] = None
    trivial_level: Optional[int] = None

@dataclass
class CraftingRequest:
    """Data class for user crafting requests"""
    character: str
    item: str
    requester: discord.Member
    timestamp: datetime

class EQDBClient:
    """Client for interacting with eqdb.net API"""
    
    # EverQuest Tradeskill ID to Name mapping (crafting/production skills only)
    TRADESKILL_NAMES = {
        55: "Fishing",
        56: "Make Poison",
        57: "Tinkering",
        58: "Research",
        59: "Alchemy",
        60: "Baking",
        61: "Tailoring",
        63: "Blacksmithing",
        64: "Fletching",
        65: "Brewing",
        68: "Jewelry Making",
        69: "Pottery"
    }
    
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.base_url = "https://eqdb.net/api/v1"
        self.items_endpoint = "/items"            # For both name and ID lookups
        self.trades_endpoint = "/trades"          # For getting recipe data by item ID
        
        # Default headers for JSON API requests
        self.headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'User-Agent': 'EverQuest-Crafting-Bot/1.0'
        }
    
    async def _make_json_request(self, url: str, params=None):
        """Make a JSON API request with proper error handling"""
        try:
            async with self.session.get(url, params=params, headers=self.headers) as response:
                # Log the request for debugging
                logger.debug(f"API Request: {response.url}")
                
                if response.status == 200:
                    # Verify content type is JSON
                    content_type = response.headers.get('content-type', '')
                    if 'application/json' not in content_type.lower():
                        logger.warning(f"Unexpected content-type: {content_type}")
                    
                    try:
                        data = await response.json()
                        logger.debug(f"API Response: {json.dumps(data, indent=2)[:500]}...")  # Log first 500 chars
                        return data
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse JSON response: {e}")
                        # Try to get raw text for debugging
                        raw_text = await response.text()
                        logger.error(f"Raw response: {raw_text[:200]}...")
                        return None
                        
                elif response.status == 404:
                    logger.info(f"Resource not found (404): {response.url}")
                    return None
                    
                elif response.status == 429:
                    logger.warning(f"Rate limited (429): {response.url}")
                    return None
                    
                else:
                    logger.warning(f"API request failed with status {response.status}: {response.url}")
                    # Try to get error details from response
                    try:
                        error_data = await response.json()
                        logger.warning(f"Error details: {error_data}")
                    except:
                        error_text = await response.text()
                        logger.warning(f"Error response: {error_text[:200]}...")
                    return None
                    
        except aiohttp.ClientError as e:
            logger.error(f"Network error during API request: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during API request: {e}")
            return None
        
    async def search_item(self, item_name: str):
        """Search for an item by name to get its ID"""
        try:
            url = f"{self.base_url}{self.items_endpoint}"
            params = {"name": item_name}
            
            logger.info(f"Searching for item by name: '{item_name}'")
            data = await self._make_json_request(url, params)
            
            if data is None:
                return None
                
            # Handle different response formats
            if isinstance(data, list):
                if len(data) > 0:
                    logger.info(f"Found {len(data)} items matching '{item_name}', using first result")
                    return data[0]  # Return first matching item
                else:
                    logger.info(f"No items found for search: '{item_name}'")
                    return None
            elif isinstance(data, dict):
                # Check if it's a single item result or a wrapper object
                if 'items' in data and isinstance(data['items'], list):
                    items = data['items']
                    if len(items) > 0:
                        logger.info(f"Found {len(items)} items matching '{item_name}', using first result")
                        return items[0]
                    else:
                        logger.info(f"No items found for search: '{item_name}'")
                        return None
                else:
                    return data  # Assume it's a single item result
            else:
                logger.warning(f"Unexpected response format for item search: {type(data)}")
                return None
                
        except Exception as e:
            logger.error(f"Error searching for item '{item_name}': {e}")
            return None
    
    async def get_item_by_id(self, item_id: str):
        """Get item details by ID"""
        try:
            url = f"{self.base_url}{self.items_endpoint}"
            params = {"id": item_id}
            
            logger.debug(f"Looking up item by ID: {item_id}")
            data = await self._make_json_request(url, params)
            
            if data is None:
                logger.debug(f"No item found for ID: {item_id}")
                return None
                
            # Handle different response formats
            if isinstance(data, list):
                if len(data) > 0:
                    return data[0]  # Return first result
                else:
                    return None
            elif isinstance(data, dict):
                # Check if it's a single item result or a wrapper object
                if 'items' in data and isinstance(data['items'], list):
                    items = data['items']
                    if len(items) > 0:
                        return items[0]
                    else:
                        return None
                else:
                    return data  # Assume it's a single item result
            else:
                logger.warning(f"Unexpected response format for item ID lookup: {type(data)}")
                return None
                
        except Exception as e:
            logger.error(f"Error looking up item ID '{item_id}': {e}")
            return None
    
    async def get_recipe(self, item_id: str):
        """Get crafting recipe for an item using the trades endpoint"""
        try:
            url = f"{self.base_url}{self.trades_endpoint}"
            params = {"id": item_id}
            
            logger.info(f"Fetching recipe for item ID: {item_id}")
            data = await self._make_json_request(url, params)
            
            if data is None:
                logger.info(f"No recipe data found for item ID: {item_id}")
                return None
            
            # Check if the response indicates no recipe exists
            if isinstance(data, dict):
                # Some APIs return empty objects or error indicators
                if not data or data.get('error') or data.get('success') is False:
                    logger.info(f"API indicates no recipe for item ID: {item_id}")
                    return None
                    
                # Parse the recipe data (this will now include component name lookups)
                recipe = await self._parse_recipe_with_names(data)
                logger.info(f"Successfully parsed recipe for: {recipe.name}")
                return recipe
            elif isinstance(data, list):
                # If multiple recipes returned, take the first one
                if len(data) > 0:
                    recipe = await self._parse_recipe_with_names(data[0])
                    logger.info(f"Successfully parsed recipe for: {recipe.name}")
                    return recipe
                else:
                    logger.info(f"Empty recipe list for item ID: {item_id}")
                    return None
            else:
                logger.warning(f"Unexpected response format for recipe: {type(data)}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching recipe for item ID '{item_id}': {e}")
            return None
    
    def _parse_recipe(self, data: Dict[str, Any]) -> Recipe:
        """Parse API response into Recipe object with robust JSON handling"""
        try:
            # Log the raw data structure for debugging
            logger.debug(f"Parsing recipe data: {json.dumps(data, indent=2)[:300]}...")
            
            # Extract fields with multiple possible field names and defaults
            name = self._get_field_value(data, ['name', 'item_name', 'recipe_name'], 'Unknown Recipe')
            skill_level = self._get_field_value(data, ['skill', 'skill_level', 'required_skill', 'skilllevel'], 0)
            profession = self._get_field_value(data, ['tradeskill', 'profession', 'trade_skill'], 'Unknown')
            crafting_station = self._get_field_value(data, ['station', 'container', 'crafting_station'], 'Unknown')
            components = self._get_field_value(data, ['components', 'ingredients', 'items'], [])
            success_rate = self._get_field_value(data, ['success_rate', 'successrate'], None)
            trivial_level = self._get_field_value(data, ['trivial', 'trivial_level', 'triviallevel'], None)
            
            # Ensure numeric fields are actually numeric
            try:
                skill_level = int(skill_level) if skill_level is not None else 0
            except (ValueError, TypeError):
                logger.warning(f"Invalid skill_level value: {skill_level}, defaulting to 0")
                skill_level = 0
                
            try:
                trivial_level = int(trivial_level) if trivial_level is not None else None
            except (ValueError, TypeError):
                logger.warning(f"Invalid trivial_level value: {trivial_level}, setting to None")
                trivial_level = None
            
            # Ensure components is a list
            if not isinstance(components, list):
                logger.warning(f"Components is not a list: {type(components)}, converting to empty list")
                components = []
            
            recipe = Recipe(
                name=str(name),
                skill_level=skill_level,
                profession=str(profession),
                crafting_station=str(crafting_station),
                components=components,
                success_rate=str(success_rate) if success_rate is not None else None,
                trivial_level=trivial_level
            )
            
            logger.debug(f"Successfully parsed recipe: {recipe.name}")
            return recipe
            
        except Exception as e:
            logger.error(f"Error parsing recipe data: {e}")
            # Return a basic recipe with error information
            return Recipe(
                name="Error parsing recipe",
                skill_level=0,
                profession="Unknown",
                crafting_station="Unknown",
                components=[]
            )
    
    def _get_field_value(self, data, field_names, default=None):
        """Get a field value from JSON data, trying multiple possible field names"""
        for field_name in field_names:
            if field_name in data and data[field_name] is not None:
                return data[field_name]
        return default

class CraftingBot(commands.Bot):
    """Main bot class for EverQuest crafting requests"""
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        
        super().__init__(
            command_prefix='!',
            intents=intents,
            description="EverQuest Crafting Request Bot"
        )
        
        self.session = None
        self.eqdb_client = None
        self.watched_forum_id = None
        
    async def setup_hook(self):
        """Initialize bot components"""
        self.session = aiohttp.ClientSession()
        self.eqdb_client = EQDBClient(self.session)
        
        # Get watched forum ID from environment
        forum_id_str = os.getenv('WATCHED_FORUM_ID')
        if forum_id_str:
            try:
                self.watched_forum_id = int(forum_id_str)
                logger.info(f"Bot will watch forum ID: {self.watched_forum_id}")
            except ValueError:
                logger.error(f"Invalid WATCHED_FORUM_ID: {forum_id_str}")
        else:
            logger.warning("WATCHED_FORUM_ID not set - bot will not auto-respond to forum posts")
            
        logger.info("Bot setup completed")
    
    async def close(self):
        """Cleanup when bot shuts down"""
        if self.session:
            await self.session.close()
        await super().close()
        logger.info("Bot shutdown completed")
    
    async def on_ready(self):
        """Called when bot is ready"""
        logger.info(f'{self.user} has connected to Discord!')
        
    async def process_forum_post(self, thread: discord.Thread):
        """Process a new forum post for crafting requests"""
        try:
            # Parse the thread title for crafting request
            parsed = self.parse_forum_post_title(thread.name)
            if not parsed:
                logger.debug(f"Forum post title doesn't match crafting request pattern: '{thread.name}'")
                return
            
            item, character = parsed
            logger.info(f"Processing forum crafting request: {item} for {character}")
            
            # Send initial processing message in the thread
            processing_embed = create_info_embed(
                "Processing Request",
                f"Searching for recipe: **{item}**\nFor character: **{character}**"
            )
            message = await thread.send(embed=processing_embed)
            
            # Search for the item by name
            item_data = await self.eqdb_client.search_item(item)
            
            if not item_data:
                embed = create_error_embed(
                    "Item Not Found",
                    f"Could not find item: **{item}**\n"
                    "Please check the spelling in your post title."
                )
                await message.edit(embed=embed)
                return
            
            # Get the item ID from search results
            item_id = item_data.get('id')
            if not item_id:
                item_id = item_data.get('item_id') or item_data.get('dbid')
                
            if not item_id:
                embed = create_error_embed(
                    "Recipe Error",
                    f"Could not retrieve item ID from search results for: **{item}**"
                )
                await message.edit(embed=embed)
                return
            
            # Get the recipe using the item ID
            recipe = await self.eqdb_client.get_recipe(str(item_id))
            
            if not recipe:
                embed = create_error_embed(
                    "Recipe Not Found",
                    f"No crafting recipe found for: **{item}**\n"
                    "This item may not be craftable."
                )
                await message.edit(embed=embed)
                return
            
            # Create and send recipe embed
            recipe_embed = create_recipe_embed(recipe, character)
            await message.edit(embed=recipe_embed)
            
            logger.info(f"Forum recipe request fulfilled: {item} for {character}")
            
        except Exception as e:
            logger.error(f"Error processing forum post: {e}")
            try:
                embed = create_error_embed(
                    "Processing Error",
                    "An error occurred while processing your request. Please try again or use manual commands."
                )
                await thread.send(embed=embed)
            except:
                pass  # Ignore errors when trying to send error message
    
    def parse_forum_post_title(self, title: str):
        """Parse forum post title for crafting requests"""
        # Pattern 1: "Item Name for Character"
        pattern1 = r'(.+?)\s+for\s+(\w+)'
        match1 = re.match(pattern1, title.strip(), re.IGNORECASE)
        
        if match1:
            item = match1.group(1).strip()
            character = match1.group(2).strip()
            return item, character
        
        # Pattern 2: "Character needs Item Name" 
        pattern2 = r'(\w+)\s+needs\s+(.+)'
        match2 = re.match(pattern2, title.strip(), re.IGNORECASE)
        
        if match2:
            character = match2.group(1).strip()
            item = match2.group(2).strip()
            return item, character
            
        # Pattern 3: "Request: Item Name - Character"
        pattern3 = r'request:?\s*(.+?)\s*[-–]\s*(\w+)'
        match3 = re.match(pattern3, title.strip(), re.IGNORECASE)
        
        if match3:
            item = match3.group(1).strip()
            character = match3.group(2).strip()
            return item, character
        
        return None
        
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        """Global error handler"""
        if isinstance(error, commands.CommandNotFound):
            return  # Ignore unknown commands
        
        logger.error(f"Command error in {ctx.command}: {error}")
        
        embed = discord.Embed(
            title="❌ Error",
            description="An error occurred while processing your request.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)

def parse_request_command(message: str):
    """Parse !request command from message - DEPRECATED - keeping for backwards compatibility only"""
    # This function is no longer used as the bot is forum-only
    return None

def create_recipe_embed(recipe: Recipe, character: str) -> discord.Embed:
    """Create Discord embed for recipe information"""
    embed = discord.Embed(
        title=f"🔨 Recipe: {recipe.name}",
        description=f"Requested for character: **{character}**",
        color=discord.Color.blue(),
        timestamp=datetime.utcnow()
    )
    
    # Add recipe details
    embed.add_field(
        name="📊 Details",
        value=f"**Profession:** {recipe.profession}\n"
              f"**Skill Level:** {recipe.skill_level}\n"
              f"**Crafting Station:** {recipe.crafting_station}",
        inline=True
    )
    
    if recipe.trivial_level:
        embed.add_field(
            name="🎯 Trivial Level",
            value=str(recipe.trivial_level),
            inline=True
        )
    
    if recipe.success_rate:
        embed.add_field(
            name="📈 Success Rate",
            value=recipe.success_rate,
            inline=True
        )
    
    # Add components with better JSON data handling
    if recipe.components:
        components_text = ""
        for component in recipe.components:
            if isinstance(component, dict):
                # Handle component as JSON object
                name = component.get('name', component.get('item_name', 'Unknown'))
                quantity = component.get('quantity', component.get('count', 1))
                components_text += f"• {quantity}x {name}\n"
            elif isinstance(component, str):
                # Handle component as simple string
                components_text += f"• {component}\n"
            else:
                # Handle unexpected format
                components_text += f"• {str(component)}\n"
        
        # Limit component list length for Discord embed limits
        if len(components_text) > 1000:
            components_text = components_text[:997] + "..."
        
        embed.add_field(
            name="📦 Required Components",
            value=components_text or "No components listed",
            inline=False
        )
    else:
        embed.add_field(
            name="📦 Required Components",
            value="No components listed",
            inline=False
        )
    
    embed.set_footer(text="Data from eqdb.net • JSON API")
    return embed

def create_error_embed(title: str, description: str) -> discord.Embed:
    """Create error embed"""
    return discord.Embed(
        title=f"❌ {title}",
        description=description,
        color=discord.Color.red()
    )

def create_info_embed(title: str, description: str) -> discord.Embed:
    """Create info embed"""
    return discord.Embed(
        title=f"ℹ️ {title}",
        description=description,
        color=discord.Color.blue()
    )

# Bot instance
bot = CraftingBot()

@bot.command(name='request')
async def request_item(ctx: commands.Context, *, args: str = None):
    """
    Handle !request command for crafting items
    Usage: !request <item name> to <character>
    Alternative: !request <character> <item> (backwards compatibility)
    """
    if not args:
        embed = create_error_embed(
            "Invalid Command",
            "Usage: `!request <item name> to <character>`\n"
            "Example: `!request Black Acrylia Pick to Mychar`\n"
            "Alternative: `!request Mychar Black Acrylia Pick`"
        )
        await ctx.send(embed=embed)
        return
    
    # Parse the command arguments
    parsed = parse_request_command(f"!request {args}")
    if not parsed:
        embed = create_error_embed(
            "Invalid Command Format",
            "Usage: `!request <item name> to <character>`\n"
            "Example: `!request Black Acrylia Pick to Mychar`\n"
            "Alternative: `!request Mychar Black Acrylia Pick`"
        )
        await ctx.send(embed=embed)
        return
    
    item, character = parsed
    
    # Send initial processing message
    processing_embed = create_info_embed(
        "Processing Request",
        f"Searching for recipe: **{item}**\nFor character: **{character}**"
    )
    message = await ctx.send(embed=processing_embed)
    
    try:
        # Search for the item by name using: /api/v1/items?name=<item>
        item_data = await bot.eqdb_client.search_item(item)
        
        if not item_data:
            embed = create_error_embed(
                "Item Not Found",
                f"Could not find item: **{item}**\n"
                "Please check the spelling and try again."
            )
            await message.edit(embed=embed)
            return
        
        # Get the item ID from search results
        item_id = item_data.get('id')
        if not item_id:
            # Try alternative field names
            item_id = item_data.get('item_id') or item_data.get('dbid')
            
        if not item_id:
            embed = create_error_embed(
                "Recipe Error",
                f"Could not retrieve item ID from search results for: **{item}**"
            )
            await message.edit(embed=embed)
            return
        
        # Get the recipe using the item ID
        recipe = await bot.eqdb_client.get_recipe(str(item_id))
        
        if not recipe:
            embed = create_error_embed(
                "Recipe Not Found",
                f"No crafting recipe found for: **{item}**\n"
                "This item may not be craftable."
            )
            await message.edit(embed=embed)
            return
        
        # Create and send recipe embed
        recipe_embed = create_recipe_embed(recipe, character)
        await message.edit(embed=recipe_embed)
        
        logger.info(f"Recipe request fulfilled: {item} for {character} by {ctx.author}")
        
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        embed = create_error_embed(
            "Processing Error",
            "An error occurred while processing your request. Please try again later."
        )
        await message.edit(embed=embed)

@bot.command(name='request_id')
async def request_item_by_id(ctx: commands.Context, character: str = None, item_id: str = None):
    """
    Handle !request_id command for crafting items using item ID
    Usage: !request_id <character> <item_id>
    """
    if not character or not item_id:
        embed = create_error_embed(
            "Invalid Command",
            "Usage: `!request_id <character> <item_id>`\n"
            "Example: `!request_id Mychar 3675`"
        )
        await ctx.send(embed=embed)
        return
    
    # Validate that item_id is numeric
    if not item_id.isdigit():
        embed = create_error_embed(
            "Invalid Item ID",
            "Item ID must be a number.\n"
            f"Received: **{item_id}**"
        )
        await ctx.send(embed=embed)
        return
    
    # Send initial processing message
    processing_embed = create_info_embed(
        "Processing Request",
        f"Fetching recipe for item ID: **{item_id}**\nFor character: **{character}**"
    )
    message = await ctx.send(embed=processing_embed)
    
    try:
        # Get the recipe directly using the item ID
        recipe = await bot.eqdb_client.get_recipe(item_id)
        
        if not recipe:
            embed = create_error_embed(
                "Recipe Not Found",
                f"No crafting recipe found for item ID: **{item_id}**\n"
                "This item may not be craftable or the ID may be incorrect."
            )
            await message.edit(embed=embed)
            return
        
        # Create and send recipe embed
        recipe_embed = create_recipe_embed(recipe, character)
        await message.edit(embed=recipe_embed)
        
        logger.info(f"Recipe request by ID fulfilled: {item_id} for {character} by {ctx.author}")
        
    except Exception as e:
        logger.error(f"Error processing request by ID: {e}")
        embed = create_error_embed(
            "Processing Error",
            "An error occurred while processing your request. Please try again later."
        )
        await message.edit(embed=embed)

@bot.command(name='forum_info')
async def forum_info(ctx: commands.Context):
    """Show current channel/forum information and bot configuration"""
    embed = discord.Embed(
        title="📍 Forum Bot Configuration",
        color=discord.Color.blue()
    )
    
    # Current channel info
    embed.add_field(
        name="Current Location",
        value=f"**Channel:** {ctx.channel.name}\n**ID:** {ctx.channel.id}\n**Type:** {ctx.channel.type}",
        inline=False
    )
    
    # Bot configuration
    if bot.watched_forum_id:
        watched_forum = bot.get_channel(bot.watched_forum_id)
        if watched_forum and isinstance(watched_forum, discord.ForumChannel):
            status = f"**Watching Forum:** #{watched_forum.name} (ID: {bot.watched_forum_id}) ✅"
        elif watched_forum:
            status = f"**Error:** Channel ID {bot.watched_forum_id} is not a forum!"
        else:
            status = f"**Watching:** Forum ID {bot.watched_forum_id} ⚠️ **Not found**"
    else:
        status = "**Forum Watching:** Disabled (manual commands only)"
    
    embed.add_field(
        name="Bot Configuration",
        value=status,
        inline=False
    )
    
    # Usage instructions
    if isinstance(ctx.channel, discord.ForumChannel):
        embed.add_field(
            name="ℹ️ Forum Setup",
            value=f"To watch this forum, set `WATCHED_FORUM_ID={ctx.channel.id}` in your .env file\n"
                  "Bot will auto-process new posts with titles like:\n"
                  "• `Black Acrylia Pick for Gandalf`\n"
                  "• `Mychar needs Ancient Spell`\n"
                  "• `Request: Item Name - Character`",
            inline=False
        )
    else:
        embed.add_field(
            name="ℹ️ Usage",
            value="This bot is designed to watch Discord forums.\n"
                  "Manual commands work in any channel.\n"
                  "For auto-processing, create posts in a forum channel.",
            inline=False
        )
    
    await ctx.send(embed=embed)

@bot.command(name='help_crafting')
async def help_crafting(ctx: commands.Context):
    """Show help information for the forum-based crafting bot"""
    embed = discord.Embed(
        title="🔨 EverQuest Forum Crafting Bot",
        description="Automated crafting recipe responses for Discord forums",
        color=discord.Color.green()
    )
    
    embed.add_field(
        name="🏛️ How It Works",
        value="Simply create a new post in the watched forum with your item and character in the title.\n"
              "The bot will automatically respond with the full crafting recipe!",
        inline=False
    )
    
    embed.add_field(
        name="📝 Commands",
        value="`!forum_info` - Show current forum configuration and help\n"
              "`!help_crafting` - Show this help message",
        inline=False
    )
    
    embed.add_field(
        name="🏷️ Forum Post Title Examples",
        value="`Black Acrylia Pick for Gandalf`\n"
              "`Mychar needs Ancient Spell: Word of Morell`\n"
              "`Request: Hardened Clay Brick - Builder`",
        inline=False
    )
    
    embed.add_field(
        name="ℹ️ Setup",
        value="• Administrator runs `!forum_info` in the crafting forum\n"
              "• Copy the Forum ID and add to bot configuration\n"
              "• Users create posts with item requests\n"
              "• Bot automatically replies with recipes!",
        inline=False
    )
    
    embed.add_field(
        name="🎯 What You Get",
        value="• Complete ingredient lists with quantities\n"
              "• Skill level and trivial level requirements\n"
              "• Tradeskill profession (Blacksmithing, Pottery, etc.)\n"
              "• Crafting station needed\n"
              "• All data sourced from eqdb.net",
        inline=False
    )
    
    await ctx.send(embed=embed)

@bot.event
async def on_message(message):
    """Handle incoming messages for manual commands"""
    if message.author == bot.user:
        return
    
    # Always process manual commands regardless of forum configuration
    await bot.process_commands(message)

def validate_environment():
    """Validate required environment variables"""
    required_vars = {
        'DISCORD_BOT_TOKEN': 'Discord bot token is required',
        'WATCHED_FORUM_ID': 'Forum ID to watch is required'
    }
    
    missing_vars = []
    for var, description in required_vars.items():
        if not os.getenv(var):
            missing_vars.append(f"  - {var}: {description}")
    
    if missing_vars:
        logger.error("Missing required environment variables:")
        for var in missing_vars:
            logger.error(var)
        logger.error("Please check your .env file or environment configuration")
        return False
    
    return True

def setup_signal_handlers(bot):
    """Setup graceful shutdown on SIGTERM/SIGINT"""
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}. Initiating graceful shutdown...")
        asyncio.create_task(bot.close())
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

def main():
    """Main entry point"""
    logger.info("Starting EverQuest Forum Crafting Bot...")
    
    # Validate environment variables
    if not validate_environment():
        sys.exit(1)
    
    # Get bot token
    token = os.getenv('DISCORD_BOT_TOKEN')
    
    # Create bot instance
    bot = CraftingBot()
    
    # Setup signal handlers for graceful shutdown
    setup_signal_handlers(bot)
    
    try:
        # Run the bot
        logger.info("Connecting to Discord...")
        bot.run(token, log_handler=None)  # We handle logging ourselves
    except discord.LoginFailure:
        logger.error("Invalid Discord bot token! Please check your DISCORD_BOT_TOKEN environment variable.")
        sys.exit(1)
    except discord.PrivilegedIntentsRequired:
        logger.error("Bot requires privileged intents! Please enable 'Message Content Intent' in Discord Developer Portal.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        sys.exit(1)
    finally:
        logger.info("Bot has shut down")

if __name__ == "__main__":
    main()