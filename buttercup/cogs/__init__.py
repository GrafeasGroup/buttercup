"""The cogs which provide the functionality to the bot."""

# Colors to use in the plots
from matplotlib import pyplot as plt

background_color = "#36393f"  # Discord background color
text_color = "white"
line_color = "white"

# Global settings for all plots
plt.rcParams["figure.facecolor"] = background_color
plt.rcParams["axes.facecolor"] = background_color
plt.rcParams["axes.labelcolor"] = text_color
plt.rcParams["axes.edgecolor"] = line_color
plt.rcParams["text.color"] = text_color
plt.rcParams["xtick.color"] = line_color
plt.rcParams["ytick.color"] = line_color
plt.rcParams["grid.color"] = line_color
plt.rcParams["grid.alpha"] = 0.8
plt.rcParams["figure.dpi"] = 200.0

# Official flair ranks
# Maybe we'll have this in the API one day,
# but we need to define the colors client-side anyway
ranks = {
    "Initiate": {"threshold": 1, "color": "#ffffff"},
    "Green": {"threshold": 50, "color": "#00ff00"},
    "Teal": {"threshold": 100, "color": "#00cccc"},
    "Purple": {"threshold": 250, "color": "#ff67ff"},
    "Gold": {"threshold": 500, "color": "#ffd700"},
    "Diamond": {"threshold": 1000, "color": "#add8e6"},
    "Ruby": {"threshold": 2500, "color": "#ff7ac2"},
    "Topaz": {"threshold": 5000, "color": "#ff7d4d"},
    "Jade": {"threshold": 10000, "color": "#31c831"},
    # This rank is not official yet, but we need it for predictions
    "Sapphire": {"threshold": 25000, "color": "#99afef"},
}
