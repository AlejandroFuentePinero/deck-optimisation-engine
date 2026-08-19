# Weekly average copies per card in the two Riddler/Fallaji builds.
#
# Four panels: the build on the rows, the board on the columns, so a card's
# mainboard line and its sideboard line are read side by side. That pairing is
# the point, since a camp that keeps the number it runs and moves where the
# copies sit has changed its mind about what the card is for, and a single
# whole-75 line reports that as nothing.
#
# Each panel carries its own y range, so a sideboard card at one copy is not
# flattened against a mainboard four-of. The cost is that heights no longer
# compare across panels, and the axes are the only thing saying so.
#
# Only the movers are drawn. The settled part of the 75 is flat by definition
# and put sixty lines behind the ones being read, so it stays in the table and
# off the plot.
#
# Called by weekly_copies.py, which writes the CSV it reads.

suppressPackageStartupMessages({
  library(ggplot2)
  library(readr)
  library(dplyr)
  library(grid)
})

args <- commandArgs(trailingOnly = TRUE)
csv_path <- args[[1]]
png_path <- args[[2]]
# Empty when the cards were named outright, in which case no threshold chose them.
threshold <- suppressWarnings(as.numeric(args[[3]]))
layout <- args[[4]]

# The validated eight-slot categorical palette, assigned in fixed order. Never
# cycled: a ninth series would be a hue nobody can tell from one already on the
# plot, so the extraction script caps the card set instead.
SERIES <- c(
  "#2a78d6", "#eb6834", "#1baf7a", "#eda100",
  "#e87ba4", "#008300", "#4a3aa7", "#e34948"
)
SURFACE <- "#fcfcfb"
INK <- "#0b0b0b"
MUTED <- "#52514e"

copies <- read_csv(csv_path, show_col_types = FALSE) |>
  mutate(
    week = as.Date(week),
    # Rows read Riddler then Fallaji, columns mainboard then sideboard, rather
    # than alphabetically, which would put the sideboard first and invert both.
    panel = factor(panel, levels = c("Riddler Goryo's", "Fallaji Goryo's")),
    board = factor(board, levels = c("mainboard", "sideboard"))
  )

# Colour follows the card, and the order is the one the extraction wrote: widest
# mover first when it chose the set, the command line's own order when the cards
# were named. Re-deriving a ranking here would undo the naming, which is what
# pins a card to its colour from one weekly run to the next.
cards <- unique(copies$card[copies$highlight])

focus <- copies[copies$highlight, ]
# Only the coloured cards become levels: the pool is eighty and the scale holds
# eight, and a factor carrying every card would put the whole pool in the legend.
focus$card <- factor(focus$card, levels = cards)

backing <- copies |>
  distinct(panel, week, lists) |>
  group_by(panel) |>
  summarise(low = min(lists), high = max(lists), .groups = "drop") |>
  mutate(text = sprintf("%s %d-%d lists/week", panel, low, high)) |>
  pull(text) |>
  paste(collapse = ", ")

plot <- ggplot(mapping = aes(week, avg_copies)) +
  geom_line(data = focus, aes(colour = card), linewidth = 0.8) +
  geom_point(data = focus, aes(colour = card), size = 1.6) +
  facet_wrap(
    vars(panel, board), nrow = 2, scales = "free_y",
    labeller = labeller(.multi_line = FALSE)
  ) +
  # Past eight the validated palette runs out. Rather than refuse, the scale
  # falls back to a spread of hues and the subtitle says so: at that count
  # colour has stopped being reliable identity and the table is the way in.
  scale_colour_manual(
    values = if (length(cards) <= length(SERIES)) {
      SERIES[seq_along(cards)]
    } else {
      grDevices::hcl.colors(length(cards), "Dark 3")
    },
    drop = FALSE
  ) +
  scale_x_date(date_breaks = "2 weeks", date_labels = "%d %b") +
  scale_y_continuous(limits = c(0, NA), expand = expansion(mult = c(0, 0.06))) +
  labs(
    title = "Average copies per list, by build and board",
    subtitle = paste0(
      "Challenge-class lists only, binned by tournament week. ",
      if (is.na(threshold)) {
        "Cards named on the command line."
      } else {
        sprintf("Non-land cards swinging %.2f+ copies.", threshold)
      },
      if (length(cards) > length(SERIES)) {
        sprintf("\n%d series past the %d colours that separate reliably: read identity off the table, not the hues.",
                length(cards), length(SERIES))
      } else {
        ""
      }
    ),
    caption = paste0(
      backing, ". Each panel has its own y range, so heights do not compare across panels.",
      "\nAn average over a handful of lists moves on one pilot.",
      " Every non-land card, drawn or not, is in weekly-copies.csv with its weekly list count."
    ),
    x = NULL, y = "copies", colour = NULL
  ) +
  theme_bw(base_size = 11) +
  theme(
    legend.position = "bottom",
    legend.justification = "left",
    legend.margin = margin(t = 4),
    legend.key = element_blank(),
    plot.background = element_rect(fill = SURFACE, colour = NA),
    panel.background = element_rect(fill = SURFACE, colour = NA),
    panel.border = element_rect(colour = "#d8d7d2", fill = NA),
    panel.grid.minor = element_blank(),
    panel.grid.major = element_line(colour = "#e8e7e2", linewidth = 0.3),
    strip.background = element_rect(fill = "#f0efea", colour = NA),
    strip.text = element_text(colour = INK, face = "bold", size = 10),
    plot.title = element_text(face = "bold", colour = INK, size = 13),
    plot.subtitle = element_text(colour = MUTED, size = 9.5, margin = margin(b = 8)),
    plot.caption = element_text(colour = MUTED, size = 8, hjust = 0, margin = margin(t = 8)),
    plot.caption.position = "plot",
    axis.title.y = element_text(colour = MUTED, size = 9),
    axis.text = element_text(colour = MUTED, size = 8.5)
  ) +
  # Four across, however many rows that takes: fixed at two rows the legend runs
  # off the page as soon as the threshold admits more than a handful of cards.
  guides(colour = guide_legend(
    ncol = 4, byrow = TRUE, override.aes = list(linewidth = 1.4, size = 2.4)
  ))

if (layout == "cards") {
  drawn <- focus
  drawn$card <- factor(drawn$card, levels = cards)
  plot <- ggplot(drawn, aes(week, avg_copies, colour = panel)) +
    geom_line(linewidth = 0.7) +
    geom_point(size = 1.4) +
    facet_grid(card ~ board, scales = "free_y", switch = "y") +
    scale_colour_manual(values = SERIES[1:2]) +
    scale_x_date(date_breaks = "4 weeks", date_labels = "%d %b") +
    scale_y_continuous(
      limits = c(0, NA), expand = expansion(mult = c(0, 0.08)), n.breaks = 3
    ) +
    labs(
      title = "Average copies per list, by card",
      subtitle = sprintf(
        "Challenge-class only, by tournament week. Non-land cards swinging %.2f+ copies.",
        threshold
      ),
      caption = paste0(
        backing, ". Each row has its own y range, so heights compare within a card and not between.",
        "\nAn average over a handful of lists moves on one pilot.",
        " Every card and its weekly list count is in weekly-copies.csv."
      ),
      x = NULL, y = "copies", colour = NULL
    ) +
    theme_bw(base_size = 10) +
    theme(
      legend.position = "bottom",
      legend.justification = "left",
      legend.key = element_blank(),
      plot.background = element_rect(fill = SURFACE, colour = NA),
      panel.background = element_rect(fill = SURFACE, colour = NA),
      panel.border = element_rect(colour = "#d8d7d2", fill = NA),
      panel.grid.minor = element_blank(),
      panel.grid.major = element_line(colour = "#e8e7e2", linewidth = 0.3),
      panel.spacing.y = unit(2, "pt"),
      strip.background = element_rect(fill = "#f0efea", colour = NA),
      strip.text.x = element_text(colour = INK, face = "bold", size = 9),
      strip.text.y.left = element_text(colour = INK, size = 8, angle = 0, hjust = 1),
      strip.placement = "outside",
      plot.title = element_text(face = "bold", colour = INK, size = 13),
      plot.subtitle = element_text(colour = MUTED, size = 9, margin = margin(b = 8)),
      plot.caption = element_text(colour = MUTED, size = 8, hjust = 0, margin = margin(t = 8)),
      plot.caption.position = "plot",
      axis.title.y = element_blank(),
      axis.text = element_text(colour = MUTED, size = 7.5)
    ) +
    guides(colour = guide_legend(override.aes = list(linewidth = 1.4, size = 2.4)))
}

height <- if (layout == "cards") {
  max(6, 0.78 * length(cards) + 2.4)
} else {
  7 + 0.22 * max(0, ceiling(length(cards) / 4) - 2)
}
ggsave(png_path, plot, width = 9, height = height, dpi = 200, bg = SURFACE, limitsize = FALSE)
