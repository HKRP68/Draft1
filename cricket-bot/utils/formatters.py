"""Text formatting utilities for Telegram messages."""


def format_coins(amount: int) -> str:
    """Format coin amount with commas."""
    return f"{amount:,}"


def format_rating_display(rating: int) -> str:
    """Format rating with OVR suffix."""
    return f"{rating} OVR"


def format_roster_entry(index: int, player_name: str, rating: int, category: str) -> str:
    """Format a single roster entry line."""
    num_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    if index < 10:
        prefix = num_emojis[index]
    else:
        prefix = f"▫️ {index + 1}."
    return f"{prefix} {player_name} - {rating} OVR | {category}"


def format_cooldown_message(command: str, remaining_seconds: int) -> str:
    """Format a cooldown message with remaining time."""
    hours = remaining_seconds // 3600
    minutes = (remaining_seconds % 3600) // 60
    seconds = remaining_seconds % 60

    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if seconds > 0 or not parts:
        parts.append(f"{seconds}s")

    time_str = " ".join(parts)
    return f"⏳ `/{command}` is on cooldown. Try again in **{time_str}**"


def format_player_info(player_data: dict, acquired_date: str = None) -> str:
    """Format full player info message for /playerinfo command."""
    buy_str = f"{player_data['buy_value']:,}"
    sell_str = f"{player_data['sell_value']:,}"

    text = (
        f"📛 **{player_data['name']}**\n"
        f"⭐ Rating: {player_data['rating']} OVR\n\n"
        f"👤 **Bio:**\n"
        f"🎯 Category: {player_data['category']}\n"
        f"🏏 Bat Hand: {player_data['bat_hand']}\n"
        f"🎳 Bowl Hand: {player_data['bowl_hand']}\n"
        f"🌀 Bowl Style: {player_data['bowl_style']}\n"
        f"🌍 Country: {player_data['country']}\n\n"
        f"📊 **Batting Stats:**\n"
        f"• Career Runs: {player_data['runs']:,}\n"
        f"• Average: {player_data['bat_avg']}\n"
        f"• Strike Rate: {player_data['strike_rate']}\n"
        f"• Centuries: {player_data['centuries']}\n\n"
        f"📊 **Bowling Stats:**\n"
        f"• Average: {player_data['bowl_avg']}\n"
        f"• Economy: {player_data['economy']}\n"
        f"• Career Wickets: {player_data['wickets']:,}\n\n"
        f"💰 **Buy Value:** {buy_str} 🪙\n"
        f"💸 **Sell Value:** {sell_str} 🪙"
    )

    if acquired_date:
        text += f"\n📅 **Acquired:** {acquired_date}"

    return text
