# 🏏 Cricket Simulator Telegram Bot

A Telegram bot for collecting and managing cricket player cards. Claim players, build your roster, spin the wheel, and collect rewards!

## Features

- **/debut** – Start your journey with 8 starting players, 5,000 coins, and 100 gems
- **/claim** – Get a random player every hour based on rarity distribution
- **/gspin** – Spin the wheel every 8 hours for coins, gems, or rare players
- **/daily** – Claim daily rewards (5,000 coins + 2 players) with streak bonuses
- **/myroster** – View your player roster (max 25 players)
- **/playerinfo [name]** – View detailed stats for any player

## Quick Start

### 1. Prerequisites
- Python 3.9+
- A Telegram Bot Token from [@BotFather](https://t.me/BotFather)
- (Optional) PostgreSQL for production
- (Optional) `wkhtmltopdf` for card image generation

### 2. Setup

```bash
cd cricket-bot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate    # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your BOT_TOKEN
```

### 3. Run

```bash
python main.py
```

### Docker Setup

```bash
docker-compose up -d
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `BOT_TOKEN` | (required) | Telegram Bot API token |
| `DATABASE_URL` | `sqlite:///./cricket_bot.db` | Database connection URL |
| `LOG_LEVEL` | `INFO` | Logging level |
| `ADMIN_PORT` | `5000` | Port for the admin panel |
| `ADMIN_USERNAME` | `admin` | Admin panel login username |
| `ADMIN_PASSWORD` | (empty) | Admin panel login password (set this to enable auth) |
| `ADMIN_SECRET_KEY` | `change-me-in-production` | Flask secret key for sessions |

## 🌐 Admin Panel (Player Management)

The bot includes a **web-based admin panel** you can open from your Android phone's browser to manage all players. Any changes you make (create, edit, delete) take effect in the bot immediately because they share the same database.

### How to Access

Once the bot is running, open your phone browser and go to:

```
http://<your-server-ip>:5000/admin
```

If you set `ADMIN_PASSWORD` in your `.env` file, the browser will ask for a username and password (HTTP Basic Auth).

### Features

- **View all players** – paginated list with search by name, filter by category/country
- **Create players** – add new players with full stats (rating, batting, bowling)
- **Edit players** – change any player field; updates apply instantly in the bot
- **Delete players** – remove players from the database
- **Mobile-friendly** – responsive Bootstrap 5 design works great on Android

### Quick Setup for Android Access

1. Deploy the bot on a server (e.g., Render, Railway, VPS) or run locally
2. Set environment variables in your `.env` file:
   ```
   ADMIN_PASSWORD=your-secure-password
   ADMIN_SECRET_KEY=some-random-string
   ```
3. Open `http://<server-ip>:5000/admin` on your Android browser
4. Log in with the username `admin` and the password you set

## Player Database

The bot includes a database of 3,200 cricket players with:
- Player ratings (50-100 OVR)
- Categories: Batsman, Bowler, All-rounder, Wicket Keeper
- Full batting and bowling statistics
- Buy/Sell values based on rating

## Rarity Distribution (/claim)

| Rating Range | Chance |
|-------------|--------|
| 50-58 OVR | 31% |
| 59-67 OVR | 20% |
| 68-76 OVR | 26% |
| 77-80 OVR | 10% |
| 81-85 OVR | 8% |
| 86-94 OVR | 4.5% |
| 95-100 OVR | 0.5% |

## Gspin Wheel Outcomes

| Color | Chance | Reward |
|-------|--------|--------|
| 🟥 Red | 55% | 5,000-10,000 coins |
| 🟨 Yellow | 30% | Player 79-85 OVR |
| 🟦 Blue | 12% | 10-50 gems |
| 🟩 Green | 2.5% | Player 85-90 OVR |
| ⭐ Purple | 0.5% | Player 90-95 OVR |

## Daily Streak

- Claim `/daily` every day to build your streak
- Miss 2 days → streak resets to 0
- Every 14 days → bonus 81-85 OVR player card

## Project Structure

```
cricket-bot/
├── config/          # Configuration (settings, database, constants)
├── database/        # Models, schemas, CRUD operations, seed data
├── services/        # Business logic (players, cards, cooldowns, streaks)
├── handlers/        # Telegram command & callback handlers
├── utils/           # Helper functions, formatters, exceptions
├── assets/          # Player data, templates, images
├── logs/            # Log files
├── main.py          # Entry point
└── requirements.txt # Dependencies
```

## License

MIT
