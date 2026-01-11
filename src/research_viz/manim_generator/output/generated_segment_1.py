"""
Generated Manim Animation Code - Segment 1

Paper: Unknown
Segment: Introduction & Problem
Scenes: 6

To render a specific scene:
    cd src/research_viz/manim_generator/output
    manim -pql generated_segment_1.py <SceneClassName>

To render all scenes:
    manim -pql generated_segment_1.py -a
"""

from manim import *
import numpy as np


################################################################################
# SEGMENT: seg_1_intro
# Introduction & Problem
################################################################################

# Scene: scene_1_example_challenge
class Scene1ExampleChallenge(Scene):
    """
    Introduces a translation example and highlights dependency + long-sentence challenge.
    Narration (snippet): Imagine you’re using a translation app. You type, “The cat sat on the mat,” and you want fluent German...
    """
    def construct(self):
        # -----------------------------
        # Create shapes (static objects)
        # -----------------------------
        # Smartphone UI frame (left)
        phone_ui = Rectangle(width=4.0, height=6.0, color=LIGHT_GRAY)
        phone_ui.shift(3 * LEFT)

        # English and German sentences (positioned near/inside the phone area)
        english_sentence_text = Text("The cat sat on the mat,", color=BLACK)
        german_sentence_text = Text("Die Katze saß auf der Matte.", color=GREEN)
        sentence_group = VGroup(english_sentence_text, german_sentence_text).arrange(DOWN, buff=0.4)
        sentence_group.shift(3 * LEFT + 0.5 * UP)

        # Token boxes for "cat" and "sat" with a linking arrow between them
        cat_word = Text("cat", color=BLACK)
        sat_word = Text("sat", color=BLACK)
        token_cat_box_rect = Rectangle(width=cat_word.width + 0.4, height=cat_word.height + 0.25, color=GOLD)
        token_sat_box_rect = Rectangle(width=sat_word.width + 0.4, height=sat_word.height + 0.25, color=GOLD)
        cat_word.move_to(token_cat_box_rect)
        sat_word.move_to(token_sat_box_rect)
        token_cat_box = VGroup(token_cat_box_rect, cat_word)
        token_sat_box = VGroup(token_sat_box_rect, sat_word)
        arrow_cat_to_sat = Tex(r"\rightarrow", color=GOLD)
        dependency_group = VGroup(token_cat_box, arrow_cat_to_sat, token_sat_box).arrange(RIGHT, buff=0.6)
        dependency_group.shift(3 * LEFT + 0.5 * DOWN)

        # Long sentence timeline represented as many small ticks (bottom)
        long_sentence_line = VGroup(*[Dot(color=GRAY).scale(0.5) for _ in range(20)])
        long_sentence_line.arrange(RIGHT, buff=0.25).to_edge(DOWN)

        # Far link arrow (dashed-style made from small dots + arrow head) above the timeline
        far_link_dashes = VGroup(*[Dot(color=ORANGE).scale(0.22) for _ in range(12)]).arrange(RIGHT, buff=0.18)
        far_link_head = Tex(r"\rightarrow", color=ORANGE)
        far_link_arrow = VGroup(far_link_dashes, far_link_head).arrange(RIGHT, buff=0.1)
        far_link_arrow.next_to(long_sentence_line, UP, buff=0.6).shift(RIGHT * 2.5)

        # Challenge label (center)
        challenge_label = Text("Connect who did what — fast, even in long sentences", color=BLACK).scale(0.9)
        challenge_label.move_to(ORIGIN + UP * 2)

        # -----------------------------
        # Animations with timing alignment
        # -----------------------------
        # 1) Fade in the phone UI at t=0.0, duration 0.8
        self.play(FadeIn(phone_ui), run_time=0.8)

        # Wait until t=2.4 to start the next animation
        self.wait(2.4 - 0.8)

        # 2) Write English then German text (stepwise) total duration 2.2
        self.play(
            AnimationGroup(
                Write(english_sentence_text),
                Write(german_sentence_text),
                lag_ratio=0.6,
            ),
            run_time=2.2,
        )

        # Wait until t=10.2 to highlight the dependency
        self.wait(10.2 - 4.6)

        # 3) Highlight CAT and SAT tokens and draw a linking arrow; reveal together (duration 1.5)
        self.play(
            FadeIn(token_cat_box),
            FadeIn(token_sat_box),
            FadeIn(arrow_cat_to_sat),
            run_time=1.5,
        )

        # Wait until t=19.0 for the long sentence reveal
        self.wait(19.0 - 11.7)

        # 4) Reveal long sentence timeline, far-distance link, and challenge label (duration 1.6)
        self.play(
            FadeIn(long_sentence_line),
            FadeIn(far_link_arrow),
            FadeIn(challenge_label),
            run_time=1.6,
        )

        # Final hold to reach the scene duration (22.4s total)
        self.wait(22.4 - 20.6)


# Scene: scene_2_rnn_limits
class Scene2RnnLimits(Scene):
    """
    Show sequential nature and long-distance weakness of RNN/LSTM.
    Narration: Traditionally, models called RNNs and LSTMs read one word at a time...
    """
    def construct(self):
        # Label (top-left)
        rnn_label = Text("RNN / LSTM (sequential)", color=RED).scale(0.9)
        rnn_label.move_to(UP * 2 + LEFT * 3)

        # Row of 10 box segments (center)
        num_segments = 10
        seg_w = 1.0
        seg_h = 0.6

        def rect_polygon(width, height):
            hw = width / 2
            hh = height / 2
            return Polygon(
                [-hw, -hh, 0],
                [ hw, -hh, 0],
                [ hw,  hh, 0],
                [-hw,  hh, 0]
            )

        rnn_sequence_row = VGroup()
        for _ in range(num_segments):
            rect = rect_polygon(seg_w, seg_h)
            rect.set_color(RED)
            rect.set_fill(color=RED, opacity=0.10)
            rnn_sequence_row.add(rect)
        rnn_sequence_row.arrange_submobjects(buff=0.15)
        rnn_sequence_row.move_to(ORIGIN)

        # Cursor (left)
        rnn_cursor = Circle(radius=0.12, color=RED)
        rnn_cursor.set_fill(RED, opacity=1)
        rnn_cursor.scale(0.7)
        rnn_cursor.move_to(rnn_sequence_row[0].get_center())

        # Whisper line (dashed, below center)
        whisper_line = DashedLine(start=LEFT * 5 + DOWN * 2, end=RIGHT * 5 + DOWN * 2, color=GRAY)

        # Slow clock (top-right), initially hidden
        slow_clock_circle = Circle(radius=0.5, color=GRAY).move_to(UP * 2 + RIGHT * 3)
        slow_clock_text = Text("⏱").scale(0.8).move_to(slow_clock_circle.get_center())
        slow_clock = VGroup(slow_clock_circle, slow_clock_text)
        slow_clock.set_opacity(0)

        # Far dependency link (dashed, initially subtle)
        p1 = rnn_sequence_row[0].get_top()
        p2 = rnn_sequence_row[-1].get_top()
        rnn_far_link = DashedLine(start=p1 + UP * 0.8, end=p2 + UP * 0.8, color=ORANGE)
        rnn_far_link.set_opacity(0.3)

        # Add all base mobjects
        self.add(rnn_label, rnn_sequence_row, rnn_cursor, whisper_line, rnn_far_link, slow_clock)

        # Timing anchor before animations
        self.wait(0.6)

        # Sequential reading: move cursor across the row over 5.0s
        # Split into two parts to better align with narration cue for the whisper analogy
        step_rt = 5.0 / (num_segments - 1)
        # First ~2.22s (4 steps)
        for i in range(1, 5):
            self.play(rnn_cursor.animate.move_to(rnn_sequence_row[i].get_center()), run_time=step_rt)

        # Whisper analogy pulse (2.0s): color pulse there-and-back
        self.play(LaggedStartMap(
            ApplyMethod, whisper_line,
            lambda m: (m.set_color, YELLOW),
            lag_ratio=0.1,
            rate_func=there_and_back,
            run_time=2.0
        ))

        # Remaining cursor steps (~2.78s)
        for i in range(5, num_segments):
            self.play(rnn_cursor.animate.move_to(rnn_sequence_row[i].get_center()), run_time=step_rt)

        # Reveal the slow clock (0.8s)
        self.play(slow_clock.animate.set_opacity(1), run_time=0.8)

        # Long-distance is hard: dim intermediates and highlight ends + far link (2.0s total)
        # Step 1: dim all intermediate boxes (0.6s)
        dims = [seg for seg in rnn_sequence_row[1:-1]]
        if dims:
            self.play(
                AnimationGroup(
                    *[seg.animate.set_opacity(0.2) for seg in dims],
                    lag_ratio=0.0
                ),
                run_time=0.6
            )
        # Step 2: highlight endpoints and the far link (1.4s)
        self.play(
            AnimationGroup(
                rnn_sequence_row[0].animate.set_color(ORANGE),
                rnn_sequence_row[-1].animate.set_color(ORANGE),
                rnn_far_link.animate.set_opacity(1),
                lag_ratio=0.0
            ),
            run_time=1.4
        )

        # Hold to fill remaining segment duration
        self.wait(2.0)


# Scene: scene_3_cnn_steps
class Scene3CnnSteps(Scene):
    """
    Show convolutional windowing and multi-step receptive field growth.
    Narration: Some newer models used convolutions, which can be faster, but still need multiple steps to connect far-apart words
    """
    def construct(self):
        # ----------------------
        # Create label (top-left)
        # ----------------------
        cnn_label = Text("Convolutions (local windows)").set_color(PURPLE).scale(0.9)
        cnn_label.to_edge(UP).to_edge(LEFT)

        # ----------------------
        # Create token sequence row (12 segments)
        # ----------------------
        segments = 12
        token_w = 0.6
        token_h = 0.5
        row_buff = 0.15
        tokens = [Rectangle(width=token_w, height=token_h) for _ in range(segments)]
        for t in tokens:
            t.set_color(PURPLE)
        cnn_sequence_row = VGroup(*tokens).arrange(RIGHT, buff=row_buff).move_to(ORIGIN)

        # ----------------------
        # Create convolution kernel window (covers 3 tokens)
        # ----------------------
        kernel_width = 3 * token_w + 2 * row_buff
        kernel_height = token_h + 0.12
        conv_kernel = Rectangle(width=kernel_width, height=kernel_height)
        conv_kernel.set_color(PURPLE)
        # Start over the first 3 tokens (centered on the 2nd token)
        start_center = tokens[1].get_center()
        conv_kernel.move_to(start_center)

        # ----------------------
        # Create stacked conv layers (3 layers) at the right side (initially not added)
        # ----------------------
        layer_w = 2.2
        layer_h = 0.4
        layer_rects = [Rectangle(width=layer_w, height=layer_h).set_color(PURPLE) for _ in range(3)]
        cnn_layers_stack = VGroup(*layer_rects).arrange(DOWN, buff=0.12)
        cnn_layers_stack.scale(0.9)
        cnn_layers_stack.next_to(cnn_sequence_row, RIGHT, buff=1.2)

        # ----------------------
        # Add initial objects
        # ----------------------
        self.add(cnn_label)
        self.add(cnn_sequence_row)
        self.add(conv_kernel)

        # ----------------------
        # Timeline control and animations
        # ----------------------
        # anim_slide_kernel: start at t = 0.4s, duration = 3.0s, sliding across the row
        # We'll split the slide so we can overlay the highlight exactly at t = 2.0s for 1.0s
        self.wait(0.4)

        # Define slide path from token 2 to token 11 (centers)
        end_center = tokens[-2].get_center()

        # Part 1 of slide: from t=0.4 to t=2.0 (1.6s)
        # progress = 1.6 / 3.0
        progress1 = 1.6 / 3.0
        mid1 = start_center + (end_center - start_center) * progress1
        self.play(conv_kernel.animate.move_to(mid1), run_time=1.6)

        # anim_faster_hint: highlight at t = 2.0s, duration = 1.0s (overlapping with continued slide)
        # Part 2 of slide concurrent with highlight: next 1.0s
        progress2 = (1.6 + 1.0) / 3.0
        mid2 = start_center + (end_center - start_center) * progress2
        self.play(
            AnimationGroup(
                conv_kernel.animate.move_to(mid2),
                Indicate(conv_kernel),
            ),
            run_time=1.0,
        )

        # Final part of slide: remaining 0.4s to reach the end
        self.play(conv_kernel.animate.move_to(end_center), run_time=0.4)

        # anim_multi_steps_needed: Fade in stacked layers at t = 3.6s for 1.2s
        # We are currently at t = 3.4s, so wait 0.2s to align with 3.6s
        self.wait(0.2)
        self.play(FadeIn(cnn_layers_stack), run_time=1.2)

        # Hold until the scene duration completes (7.2s total)
        self.wait(7.2 - (0.4 + 1.6 + 1.0 + 0.4 + 0.2 + 1.2))


# Scene: scene_4_transformer_attention
from manim import *
import math


class Scene4TransformerAttention(Scene):
    """
    Introduce Transformer attention with a split-screen: old sequential chain (left) vs all-to-all attention (right),
    plus paper title and a caption. Animations are timed to narration offsets.
    """
    def construct(self):
        # =============================
        # Create shapes (all elements)
        # =============================
        # Title at top center
        paper_title = Text("Attention Is All You Need", color=WHITE).scale(1.0)
        paper_title.to_edge(UP)

        # Transformer label slightly below center
        transformer_label = Text("Transformer", color=BLUE).scale(0.9)
        transformer_label.move_to(DOWN * 0.6)

        # Old sequential chain: 6 small boxes arranged horizontally on the left
        chain_boxes = VGroup(
            *[Rectangle(width=0.6, height=0.4).set_color(RED) for _ in range(6)]
        )
        chain_boxes.arrange(direction=RIGHT, buff=0.15)
        chain_boxes.scale(0.8)
        chain_boxes.move_to(LEFT * 3)
        old_chain_small = chain_boxes

        # Right side: attention graph (6 nodes, all-to-all connections)
        # We'll place nodes on a circle and connect every pair with thin rectangles (as edges)
        graph_center = RIGHT * 3
        node_radius = 0.08
        circle_radius = 1.7

        nodes = []
        for k in range(6):
            angle = 2 * PI * k / 6
            pos = graph_center + circle_radius * (math.cos(angle) * RIGHT + math.sin(angle) * UP)
            c = Circle(radius=node_radius, color=BLUE)
            c.move_to(pos)
            nodes.append(c)
        nodes_group = VGroup(*nodes)

        # Build dense connections (all-to-all)
        edges = []
        node_centers = [n.get_center() for n in nodes]
        for i in range(6):
            for j in range(i + 1, 6):
                start = node_centers[i]
                end = node_centers[j]
                dx = end[0] - start[0]
                dy = end[1] - start[1]
                dist = math.hypot(dx, dy)
                theta = math.atan2(dy, dx)
                e = Rectangle(width=dist, height=0.03).set_color(BLUE)
                # Rotate first, then place at midpoint
                e.rotate(theta)
                e.move_to((start + end) / 2)
                e.set_opacity(0.4)
                edges.append(e)
        edges_group = VGroup(*edges)
        attention_graph = VGroup(edges_group, nodes_group)

        # Conversation table (round table) under/around the graph on the right
        table_circle = Circle(radius=2.0, color=BLUE).scale(0.9)
        table_circle.move_to(graph_center)
        table_circle.set_opacity(0.6)

        # Caption at bottom-right
        attention_caption = Text(
            "Every word can attend to every other, simultaneously",
            color=BLUE
        ).scale(0.8)
        attention_caption.to_edge(DOWN)
        attention_caption.to_edge(RIGHT)

        # =============================
        # Add base elements visible from start
        # =============================
        # Old chain is present from the beginning as a reminder
        self.add(old_chain_small)

        # =============================
        # Timeline-aligned animations
        # =============================
        # 0.0s: Title in (0.8s)
        self.play(FadeIn(paper_title), run_time=0.8)

        # 0.8s: Transformer label in (0.8s)
        self.play(FadeIn(transformer_label), run_time=0.8)

        # Wait until 3.2s to contrast old vs new (current time = 1.6s)
        self.wait(3.2 - 1.6)

        # 3.2s: Highlight old chain by dimming it (2.0s)
        self.play(old_chain_small.animate.set_opacity(0.25), run_time=2.0)

        # Wait until 6.0s for attention reveal (current time = 5.2s)
        self.wait(6.0 - 5.2)

        # 6.0s: Reveal attention graph (nodes + dense connections) simultaneously (3.0s)
        self.play(FadeIn(attention_graph), run_time=3.0)

        # Wait until 12.6s for the table analogy (current time = 9.0s)
        self.wait(12.6 - 9.0)

        # 12.6s: Show round table and caption (2.0s)
        self.play(FadeIn(table_circle), FadeIn(attention_caption), run_time=2.0)

        # Wait until 16.8s for cross-out of old chain (current time = 14.6s)
        self.wait(16.8 - 14.6)

        # 16.8s: Cross-out effect on the old chain (1.6s)
        cross_w = old_chain_small.get_width() * 1.3
        cross_h = 0.06
        cross1 = Rectangle(width=cross_w, height=cross_h, color=RED)
        cross2 = Rectangle(width=cross_w, height=cross_h, color=RED)
        cross1.rotate(PI / 4)
        cross2.rotate(-PI / 4)
        cross1.move_to(old_chain_small.get_center())
        cross2.move_to(old_chain_small.get_center())
        self.play(FadeIn(cross1), FadeIn(cross2), run_time=1.6)

        # Hold until end of segment duration (24.8s total; current time = 18.4s)
        self.wait(24.8 - 18.4)


# Scene: scene_5_why_it_matters
class Scene5WhyItMatters(Scene):
    """
    Motivate with speed, parallelism, long-range capture, and practical gains.
    Narration: Why does this matter? It trains much faster because many operations happen in parallel, and it captures long-range connections better. Practically, that means better translations, more coherent summaries, and smarter assistants—all with shorter training times
    """
    def construct(self):
        # ========= Create shapes =========
        # Title
        why_label = Text("Why this matters", color=WHITE).scale(0.9)
        why_label.to_edge(UP)

        # Parallel ops grid (3 x 5) on the left
        rows, cols = 3, 5
        cell_w, cell_h = 0.5, 0.32
        grid_hbuff, grid_vbuff = 0.12, 0.12
        row_groups = []
        for r in range(rows):
            cells = [
                Rectangle(
                    width=cell_w,
                    height=cell_h,
                    stroke_color=TEAL_C,
                    fill_color=TEAL_A,
                    fill_opacity=0.35,
                )
                for c in range(cols)
            ]
            row = VGroup(*cells).arrange(RIGHT, buff=grid_hbuff)
            row_groups.append(row)
        parallel_ops_grid = VGroup(*row_groups).arrange(DOWN, buff=grid_vbuff)
        parallel_ops_grid.to_edge(LEFT).shift(UP * 0.5)

        # Speed bar (progress bar) under the grid on the left
        bar_width = 3.2
        bar_height = 0.28
        speed_bar_outline = Rectangle(width=bar_width, height=bar_height, stroke_color=GREEN_A)
        speed_bar_outline.next_to(parallel_ops_grid, DOWN, buff=0.5)

        # Fill starts at ~0%
        start_w = 0.02
        speed_bar = Rectangle(
            width=start_w,
            height=bar_height,
            stroke_width=0,
            fill_color=GREEN_A,
            fill_opacity=1.0,
        )
        # Align fill to the left edge of the outline
        left_edge = speed_bar_outline.get_left()
        speed_bar.move_to(left_edge + RIGHT * (start_w / 2))

        # Target fill at ~100%
        speed_bar_target = Rectangle(
            width=bar_width,
            height=bar_height,
            stroke_width=0,
            fill_color=GREEN_A,
            fill_opacity=1.0,
        )
        speed_bar_target.move_to(left_edge + RIGHT * (bar_width / 2))

        # Attention heatmap (6x6 grid) in center
        hm_n = 6
        hm_cell = 0.35
        hm_hbuff, hm_vbuff = 0.06, 0.06
        # Use a blue/teal-like gradient with TEAL shades from examples
        grad_colors = [TEAL_A, TEAL_B, TEAL_C, TEAL_D, TEAL_E]
        heat_rows = []
        # Build base heatmap cells
        for i in range(hm_n):
            cells = []
            for j in range(hm_n):
                # Map distance from diagonal to a color index (off-diagonal darker)
                dist = abs(i - j)
                idx = min(dist, len(grad_colors) - 1)
                cell = Rectangle(
                    width=hm_cell,
                    height=hm_cell,
                    stroke_color=WHITE,
                    stroke_width=1,
                    fill_color=grad_colors[idx],
                    fill_opacity=0.85,
                )
                cells.append(cell)
            row = VGroup(*cells).arrange(RIGHT, buff=hm_hbuff)
            heat_rows.append(row)
        attention_heatmap = VGroup(*heat_rows).arrange(DOWN, buff=hm_vbuff)
        attention_heatmap.move_to(ORIGIN)

        # Overlay for highlighting off-diagonal cells
        offdiag_overlay_cells = []
        for i, row in enumerate(heat_rows):
            for j, base_cell in enumerate(row):
                if i != j:
                    overlay = base_cell.copy()
                    overlay.stroke_color = YELLOW
                    overlay.fill_color = YELLOW
                    overlay.fill_opacity = 0.25
                    offdiag_overlay_cells.append(overlay)
        offdiag_overlay = VGroup(*offdiag_overlay_cells)
        # Keep overlay hidden initially (will FadeIn later)
        offdiag_overlay.set_opacity(0)  # initial invisibility; FadeIn will reveal

        # Outcome texts on the right
        outcome_translations = Text("Better translations", color=WHITE).scale(0.8)
        outcome_summaries = Text("More coherent summaries", color=WHITE).scale(0.8)
        outcome_assistants = Text("Smarter assistants", color=WHITE).scale(0.8)
        outcomes_group = VGroup(outcome_translations, outcome_summaries, outcome_assistants)
        outcomes_group.arrange(DOWN, aligned_edge=LEFT, buff=0.35)
        outcomes_group.next_to(attention_heatmap, RIGHT, buff=1.0)

        shorter_time_note = Text("Shorter training times", color=GREEN_A).scale(0.8)
        shorter_time_note.to_edge(DR)

        # Group all outcomes to reveal together
        all_outcomes = VGroup(outcome_translations, outcome_summaries, outcome_assistants, shorter_time_note)

        # ========= Animations (timed to narration) =========
        # t = 0.0 -> 0.8: Write the title
        self.play(Write(why_label), run_time=0.8)

        # Wait to reach t = 1.0
        self.wait(0.2)

        # At t = 1.0: add the progress bar components so Transform can run
        self.add(speed_bar_outline, speed_bar)
        # t = 1.0 -> 2.4: Reveal many blocks (grid) and fill the bar quickly
        self.play(
            FadeIn(parallel_ops_grid),
            Transform(speed_bar, speed_bar_target),
            run_time=1.4,
        )

        # Wait to reach t = 2.6
        self.wait(0.2)

        # t = 2.6 -> 3.6: Fade in attention heatmap
        self.play(FadeIn(attention_heatmap), run_time=1.0)

        # Wait to reach t = 3.8
        self.wait(0.2)

        # t = 3.8 -> 5.0: Emphasize off-diagonal cells (long-range links)
        # Reveal overlay highlighting off-diagonals
        self.play(FadeIn(offdiag_overlay), run_time=1.2)

        # Wait to reach t = 5.2
        self.wait(0.2)

        # t = 5.2 -> 6.6: Reveal practical outcomes
        self.play(FadeIn(all_outcomes), run_time=1.4)

        # Fill remaining time to the segment duration (14.0 seconds)
        self.wait(14.0 - 6.6)


# Scene: scene_6_roadmap
class Scene6Roadmap(Scene):
    """
    Roadmap: attention -> self-attention -> transformer -> translation example.
    Narration: In this video, we’ll first build the tools to understand attention and self-attention, then we’ll see how the Transformer uses them to turn “The cat sat on the mat” into fluent German.
    """
    def construct(self):
        # Helper to make a labeled step box (rectangle + label)
        def make_step_box(label_text, color):
            box = Rectangle(width=4.0, height=1.2, color=color)
            label = Text(label_text).scale(0.6)
            grp = VGroup(box, label)
            label.move_to(box.get_center())
            return grp

        # Create roadmap steps (boxes with labels)
        roadmap_step1 = make_step_box("Attention basics", TEAL).scale(0.9)
        roadmap_step2 = make_step_box("Self-attention", TEAL).scale(0.9)
        roadmap_step3 = make_step_box("Transformer", BLUE).scale(0.9)
        roadmap_step4 = make_step_box("End-to-end translation example", GREEN).scale(0.9)

        # Arrows between steps using Tex arrows (keeps to provided examples)
        arrow12 = Tex(r"\rightarrow").scale(1.2).set_color(GRAY)
        arrow23 = Tex(r"\rightarrow").scale(1.2).set_color(GRAY)
        arrow34 = Tex(r"\rightarrow").scale(1.2).set_color(GRAY)
        roadmap_arrows = VGroup(arrow12, arrow23, arrow34)

        # Arrange the flow horizontally: step1 -> step2 -> step3 -> step4
        flow = VGroup(roadmap_step1, arrow12, roadmap_step2, arrow23, roadmap_step3, arrow34, roadmap_step4)
        flow.arrange(RIGHT, buff=0.6)
        flow.move_to(ORIGIN + UP * 0.8)

        # Bottom: English -> German with translation arrow
        english_sentence_text = Text("The cat sat on the mat,", color=WHITE).scale(0.9)
        german_sentence_text = Text("Die Katze saß auf der Matte.", color=GREEN).scale(0.9)
        translate_arrow = Tex(r"\Rightarrow").scale(1.2).set_color(GREEN)

        english_sentence_text.to_edge(DOWN).to_edge(LEFT)
        german_sentence_text.to_edge(DOWN).to_edge(RIGHT)
        translate_arrow.to_edge(DOWN).shift(UP * 0.6)

        # Timeline control to align with narration offsets
        current_time = 0.0

        # Start offset before first reveal
        self.wait(0.2)
        current_time += 0.2

        # 1) Reveal first two roadmap steps with connecting arrows (create -> FadeIn)
        self.play(
            FadeIn(roadmap_step1),
            FadeIn(roadmap_step2),
            FadeIn(roadmap_arrows),
            run_time=1.2,
        )
        current_time += 1.2

        # Wait until next narration cue at 3.2s
        wait_to_3_2 = max(0.0, 3.2 - current_time)
        if wait_to_3_2 > 0:
            self.wait(wait_to_3_2)
            current_time += wait_to_3_2

        # 2) Bring in Transformer step
        self.play(FadeIn(roadmap_step3), run_time=0.8)
        current_time += 0.8

        # Wait until next narration cue at 5.4s
        wait_to_5_4 = max(0.0, 5.4 - current_time)
        if wait_to_5_4 > 0:
            self.wait(wait_to_5_4)
            current_time += wait_to_5_4

        # 3) Reveal final step and show planned translation path
        self.play(
            FadeIn(roadmap_step4),
            FadeIn(english_sentence_text),
            FadeIn(german_sentence_text),
            FadeIn(translate_arrow),
            run_time=1.6,
        )
        current_time += 1.6

        # Hold until the segment duration ends (12.8s total)
        total_duration = 12.8
        remaining = max(0.0, total_duration - current_time)
        if remaining > 0:
            self.wait(remaining)


