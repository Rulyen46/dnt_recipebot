# EverQuest Forum Crafting Bot

A Discord bot that automatically processes crafting requests posted in Discord forums and responds with detailed recipes from eqdb.net.

## Features

- **Automatic Forum Processing**: Monitors Discord forums for new crafting request posts
- **Smart Title Parsing**: Recognizes multiple post title formats for item and character requests
- **Complete Recipe Details**: Beautiful Discord embeds showing:
  - Required components with quantities and actual item names
  - Skill level requirements and trivial levels
  - Profession mapping (Blacksmithing, Pottery, etc.)
  - Crafting station names (looked up from container IDs)
- **Robust JSON API Handling**: Full application/json support with error recovery
- **Comprehensive Logging**: Detailed monitoring and debugging information
- **Zero Commands Required**: Users simply create forum posts, bot responds automatically

## How It Works

1. **User creates a forum post** with title like: "Black Acrylia Pick for Gandalf"
2. **Bot detects the new post** and parses the title for item and character
3. **Bot searches eqdb.net** for the item and retrieves the complete recipe
4. **Bot replies in the thread** with a detailed recipe embed
5. **User gets everything they need** - ingredients, skill levels, crafting station, etc.

## Setup

### Prerequisites

- Python 3.8 or higher
- Discord bot token
- Access to eqdb.net API (endpoints to be added later)

### Installation

1. **Clone or download the bot files**

2. **Run the setup script**:
   ```bash
   python setup.py
   ```

3. **Configure your bot token and forum**:
   - Edit the `.env` file created by setup
   - Add your Discord bot token:
     ```
     DISCORD_BOT_TOKEN=your_actual_bot_token_here
     ```
   - **Configure the forum to watch** (REQUIRED):
     ```
     WATCHED_FORUM_ID=123456789012345678
     ```

4. **Update API endpoints** (partially completed):
   - The main recipe endpoint is now configured: `https://eqdb.net/api/v1/trades?id={item_id}`
   - Still need to configure the item search endpoint in `EQDBClient` class:
     - Replace `PLACEHOLDER_ITEMS_SEARCH_ENDPOINT` 
     - Update `PLACEHOLDER_SEARCH_PARAMS` based on actual search API format
     - Adjust `PLACEHOLDER_ITEM_ID_FIELD` based on search response structure

### Manual Installation

If you prefer manual setup:

```bash
# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.template .env

# Edit .env with your bot token
```

## Usage

### Forum Setup

**To configure the bot for your crafting forum:**

1. **Get the Forum ID**:
   - Navigate to your Discord forum channel
   - Run `!forum_info` in the forum
   - Copy the Forum ID from the bot's response

2. **Configure the bot**:
   - Add `WATCHED_FORUM_ID=<your_forum_id>` to your `.env` file
   - Restart the bot

3. **Users create posts**:
   - Users create new forum posts with item requests in the title
   - Bot automatically responds with complete recipe information

### Forum Post Formats

Users can create posts with titles in any of these formats:

- **`Black Acrylia Pick for Gandalf`**
- **`Mychar needs Ancient Spell: Word of Morell`**  
- **`Request: Hardened Clay Brick - Builder`**

The bot will automatically parse the title, extract the item name and character, then respond with the complete crafting recipe.

### Administrative Commands

- **!forum_info**: Show current forum configuration and setup instructions
- **!help_crafting**: Show help information about the bot

### API Endpoints Used

The bot uses these eqdb.net API endpoints:

**Item Search by Name:**
```
https://eqdb.net/api/v1/items?name=Black%20Acrylia%20Pick
```

**Item Lookup by ID:**
```
https://eqdb.net/api/v1/items?id=17731
```

**Recipe/Trade Data:**
```
https://eqdb.net/api/v1/trades?id=3675
```

### Starting the Bot

```bash
python eq_crafting_bot.py
```

### Example Workflow

**Complete Auto-Processing Flow:**
1. User creates forum post with title: `Black Acrylia Pick for Gandalf`
2. Bot detects new post in watched forum via Discord event
3. Bot parses title to extract: Item = "Black Acrylia Pick", Character = "Gandalf"
4. Bot searches eqdb.net: `https://eqdb.net/api/v1/items?name=Black%20Acrylia%20Pick`
5. Bot gets item ID from search results
6. Bot fetches recipe: `https://eqdb.net/api/v1/trades?id={item_id}`
7. Bot looks up each component name: `https://eqdb.net/api/v1/items?id={component_id}`
8. Bot looks up crafting station name from container ID
9. Bot maps tradeskill ID (e.g., 63) to profession name (e.g., "Blacksmithing")
10. Bot replies in forum thread with complete recipe embed

**Recipe Embed Contents:**
- Recipe name and target character
- Profession (e.g., "Blacksmithing", "Pottery") - mapped from tradeskill IDs
- Skill level required and trivial level
- Crafting station name (looked up from container ID)
- Complete list of required components with quantities and actual item names

## Code Structure

### Main Components

- **`CraftingBot`**: Main bot class extending discord.py commands.Bot
- **`EQDBClient`**: API client for interacting with eqdb.net
- **`Recipe`**: Data class for recipe information
- **`CraftingRequest`**: Data class for user requests

### Key Features

- **Async/await patterns**: All API calls are non-blocking
- **Type hints**: Full type annotations for better code clarity
- **Error handling**: Comprehensive try/catch blocks with logging
- **Clean separation**: API client separated from bot logic
- **Configurable**: Environment variables for sensitive data

## API Integration Points

The bot now uses the actual eqdb.net API structure with the base URL `https://eqdb.net/api/v1`.

**JSON API Support:**
- Full `application/json` content-type handling
- Proper request headers for JSON APIs
- Robust JSON parsing with error recovery
- Support for multiple JSON response formats (arrays, objects, nested data)
- Detailed API logging for debugging

### ✅ Fully Configured Endpoints:
- **Item Search by Name**: `https://eqdb.net/api/v1/items?name={item_name}` - ✅ Ready
- **Item Lookup by ID**: `https://eqdb.net/api/v1/items?id={item_id}` - ✅ Ready  
- **Trades/Recipes**: `https://eqdb.net/api/v1/trades?id={item_id}` - ✅ Ready
- **Tradeskill ID Mapping**: Complete mapping of all crafting tradeskills - ✅ Ready

### 🔧 Implementation Details:

**Two-Stage Item Resolution:**
1. **User Request**: `!request Black Acrylia Pick to Gandalf`
   - Uses `?name=` parameter to find item by name
   - Extracts item ID from search results
   
2. **Component Resolution**: For each recipe component
   - Uses `?id=` parameter to get component names 
   - Converts item IDs to readable names in recipe display

**Tradeskill Mapping:**
- Maps numeric tradeskill IDs (e.g., `63`) to names (e.g., `"Blacksmithing"`)
- Covers all EverQuest crafting/production skills
- Graceful fallback for unknown skill IDs

## Logging

The bot logs to both console and file (`eq_bot.log`):
- Info: Successful operations and bot status
- Warning: Non-critical issues like failed API calls
- Error: Critical errors and exceptions

## Discord Permissions

Your bot needs the following permissions in the Discord server:
- **View Channels**: To see the forum and new posts
- **Send Messages**: To reply in forum threads
- **Embed Links**: To send rich recipe embeds
- **Read Message History**: To detect new forum posts
- **Create Public Threads**: For forum post interaction (usually automatic)

## Development

### Architecture

The bot is designed as a pure forum processor:

1. **Forum Monitoring**: Uses Discord's `on_thread_create` event to detect new posts
2. **Title Parsing**: Smart regex patterns to extract item names and characters
3. **API Integration**: Automated eqdb.net lookups with full error handling
4. **Response Generation**: Rich Discord embeds with complete recipe information

### Key Features

- **Environment variables** for configuration
- **Dataclasses** for structured data
- **Type hints** throughout the codebase
- **Async/await** for all I/O operations
- **Comprehensive error handling** with user feedback
- **Detailed logging** for monitoring and debugging
- **Clean separation** of API client from bot logic

## Troubleshooting

### Common Issues

1. **Bot not responding to forum posts**: 
   - Verify `WATCHED_FORUM_ID` is set correctly in `.env`
   - Use `!forum_info` in the forum to verify configuration
   - Ensure the channel is actually a Discord forum, not a regular channel
   - Check that bot has permission to view and post in the forum
   - Verify post titles match the expected patterns (see examples above)

2. **Bot token errors**: Ensure your `.env` file has the correct Discord bot token

3. **Import errors**: Run `pip install -r requirements.txt`

4. **Permission errors**: 
   - Check bot permissions in Discord server
   - Ensure bot can read messages and create posts in the forum
   - Bot needs "Send Messages", "Embed Links", and "Read Message History" permissions

5. **API errors**: All eqdb.net endpoints are pre-configured and should work automatically

6. **JSON parsing errors**: Check logs for malformed API responses

7. **Rate limiting**: Bot handles 429 responses automatically

### Logs

Check `eq_bot.log` for detailed error information and bot activity. The bot logs:
- **DEBUG**: API requests/responses, JSON parsing details, and forum post processing steps
- **INFO**: Successful operations, search results, forum configuration, and new post detection
- **WARNING**: Non-critical issues like 404s, rate limits, or missing forum configuration
- **ERROR**: Critical errors, JSON parsing failures, and forum processing errors

## Contributing

The bot is production-ready with all eqdb.net endpoints configured. Future enhancements could include:

1. **Additional title parsing patterns** for different request formats
2. **Reaction-based interactions** for recipe variations or alternatives
3. **Caching** for frequently requested recipes
4. **Multi-server support** with per-server forum configuration

## License

This project is provided as-is for EverQuest community use.