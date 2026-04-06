"""Card image generation using ImgKit (HTML → PNG)."""

import logging
import os
import tempfile
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Try to import imgkit; if unavailable, card generation will fall back to text
try:
    import imgkit

    IMGKIT_AVAILABLE = True
except ImportError:
    IMGKIT_AVAILABLE = False
    logger.warning("imgkit not installed. Card images will fall back to text.")


CARD_HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    width: 400px;
    height: 700px;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
    color: #fff;
    overflow: hidden;
  }}
  .card {{
    width: 400px;
    height: 700px;
    padding: 20px;
    display: flex;
    flex-direction: column;
    align-items: center;
  }}
  .header {{
    font-size: 18px;
    font-weight: bold;
    color: #FFD700;
    margin-bottom: 10px;
    letter-spacing: 2px;
  }}
  .player-image {{
    width: 120px;
    height: 120px;
    border-radius: 50%;
    border: 3px solid {tier_color};
    background: #2a2a4a;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 48px;
    margin-bottom: 10px;
    overflow: hidden;
  }}
  .player-image img {{
    width: 100%;
    height: 100%;
    object-fit: cover;
  }}
  .player-name {{
    font-size: 24px;
    font-weight: bold;
    text-align: center;
    margin-bottom: 5px;
    text-shadow: 1px 1px 3px rgba(0,0,0,0.5);
  }}
  .rating {{
    font-size: 20px;
    font-weight: bold;
    color: {tier_color};
    margin-bottom: 3px;
  }}
  .tier-badge {{
    display: inline-block;
    padding: 3px 14px;
    border-radius: 12px;
    background: {tier_color};
    color: #000;
    font-weight: bold;
    font-size: 13px;
    margin-bottom: 12px;
  }}
  .info-section {{
    width: 100%;
    background: rgba(255,255,255,0.08);
    border-radius: 10px;
    padding: 10px 15px;
    margin-bottom: 8px;
  }}
  .info-row {{
    display: flex;
    justify-content: space-between;
    padding: 3px 0;
    font-size: 13px;
    border-bottom: 1px solid rgba(255,255,255,0.06);
  }}
  .info-row:last-child {{ border-bottom: none; }}
  .info-label {{ color: #aaa; }}
  .info-value {{ font-weight: bold; }}
  .stats-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 4px 20px;
    width: 100%;
    background: rgba(255,255,255,0.08);
    border-radius: 10px;
    padding: 10px 15px;
    margin-bottom: 8px;
  }}
  .stat-item {{
    display: flex;
    justify-content: space-between;
    font-size: 12px;
    padding: 2px 0;
  }}
  .stat-label {{ color: #aaa; }}
  .stat-value {{ font-weight: bold; }}
  .footer {{
    font-size: 11px;
    color: #888;
    margin-top: auto;
  }}
</style>
</head>
<body>
<div class="card">
  <div class="header">🏏 CRICKET CARD</div>

  <div class="player-image">
    {player_image_html}
  </div>

  <div class="player-name">{player_name}</div>
  <div class="rating">⭐ {rating} OVR</div>
  <div class="tier-badge">{tier_emoji} {tier_name}</div>

  <div class="info-section">
    <div class="info-row">
      <span class="info-label">🎯 Category</span>
      <span class="info-value">{category}</span>
    </div>
    <div class="info-row">
      <span class="info-label">🏏 Bat Hand</span>
      <span class="info-value">{bat_hand}</span>
    </div>
    <div class="info-row">
      <span class="info-label">🎳 Bowl Hand</span>
      <span class="info-value">{bowl_hand}</span>
    </div>
    <div class="info-row">
      <span class="info-label">🌀 Bowl Style</span>
      <span class="info-value">{bowl_style}</span>
    </div>
    <div class="info-row">
      <span class="info-label">💰 Card Value</span>
      <span class="info-value">{buy_value} 🪙</span>
    </div>
    <div class="info-row">
      <span class="info-label">💸 Sell Value</span>
      <span class="info-value">{sell_value} 🪙</span>
    </div>
  </div>

  <div class="stats-grid">
    <div class="stat-item">
      <span class="stat-label">Bat Rating</span>
      <span class="stat-value">{bat_rating}</span>
    </div>
    <div class="stat-item">
      <span class="stat-label">Bowl Rating</span>
      <span class="stat-value">{bowl_rating}</span>
    </div>
    <div class="stat-item">
      <span class="stat-label">Bat Avg</span>
      <span class="stat-value">{bat_avg}</span>
    </div>
    <div class="stat-item">
      <span class="stat-label">Strike Rate</span>
      <span class="stat-value">{strike_rate}</span>
    </div>
    <div class="stat-item">
      <span class="stat-label">Bowl Avg</span>
      <span class="stat-value">{bowl_avg}</span>
    </div>
    <div class="stat-item">
      <span class="stat-label">Economy</span>
      <span class="stat-value">{economy}</span>
    </div>
  </div>

  <div class="footer">📅 {date_claimed}</div>
</div>
</body>
</html>"""


def generate_card(player_data: dict, output_path: Optional[str] = None) -> Optional[str]:
    """
    Generate a player card image from player data.

    Args:
        player_data: Dictionary containing player stats (from get_player_stats).
        output_path: Optional path to save the PNG. If None, a temp file is used.

    Returns:
        Path to the generated PNG file, or None if generation failed.
    """
    if not IMGKIT_AVAILABLE:
        logger.warning("imgkit not available, skipping card generation")
        return None

    try:
        # Build player image HTML
        if player_data.get("image_url"):
            player_image_html = f'<img src="{player_data["image_url"]}" alt="{player_data["name"]}">'
        else:
            player_image_html = "🏏"

        # Format values
        buy_str = f"{player_data['buy_value']:,}"
        sell_str = f"{player_data['sell_value']:,}"
        date_str = datetime.now(timezone.utc).strftime("%d %b %Y")

        # Fill template
        html = CARD_HTML_TEMPLATE.format(
            tier_color=player_data["tier_color"],
            player_image_html=player_image_html,
            player_name=player_data["name"],
            rating=player_data["rating"],
            tier_emoji=player_data["tier_emoji"],
            tier_name=player_data["tier_name"],
            category=player_data["category"],
            bat_hand=player_data["bat_hand"],
            bowl_hand=player_data["bowl_hand"],
            bowl_style=player_data["bowl_style"],
            buy_value=buy_str,
            sell_value=sell_str,
            bat_rating=player_data["bat_rating"],
            bowl_rating=player_data["bowl_rating"],
            bat_avg=player_data["bat_avg"],
            strike_rate=player_data["strike_rate"],
            bowl_avg=player_data["bowl_avg"],
            economy=player_data["economy"],
            date_claimed=date_str,
        )

        # Determine output path
        if output_path is None:
            fd, output_path = tempfile.mkstemp(suffix=".png", prefix="cricket_card_")
            os.close(fd)

        # ImgKit options
        options = {
            "format": "png",
            "width": 400,
            "height": 700,
            "quality": 100,
            "enable-local-file-access": "",
            "quiet": "",
        }

        imgkit.from_string(html, output_path, options=options)
        logger.info("Card generated: %s for player %s", output_path, player_data["name"])
        return output_path

    except Exception as e:
        logger.error("Failed to generate card for %s: %s", player_data.get("name", "unknown"), e)
        return None


def format_card_text(player_data: dict) -> str:
    """Format player data as text (fallback when image generation fails)."""
    buy_str = f"{player_data['buy_value']:,}"
    sell_str = f"{player_data['sell_value']:,}"

    return (
        f"🏏 *CRICKET CARD*\n\n"
        f"📛 *{player_data['name']}*\n"
        f"⭐ *Rating:* {player_data['rating']} OVR\n"
        f"{player_data['tier_emoji']} *Tier:* {player_data['tier_name']}\n\n"
        f"🎯 *Category:* {player_data['category']}\n"
        f"🏏 *Bat Hand:* {player_data['bat_hand']}\n"
        f"🎳 *Bowl Hand:* {player_data['bowl_hand']}\n"
        f"🌀 *Bowl Style:* {player_data['bowl_style']}\n"
        f"💰 *Card Value:* {buy_str} 🪙\n"
        f"💸 *Sell Value:* {sell_str} 🪙\n\n"
        f"📊 *Stats:*\n"
        f"• Bat Rating: {player_data['bat_rating']}\n"
        f"• Bowl Rating: {player_data['bowl_rating']}\n"
        f"• Bat Avg: {player_data['bat_avg']}\n"
        f"• Strike Rate: {player_data['strike_rate']}\n"
        f"• Bowl Avg: {player_data['bowl_avg']}\n"
        f"• Economy: {player_data['economy']}"
    )
