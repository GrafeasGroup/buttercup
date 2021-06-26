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
