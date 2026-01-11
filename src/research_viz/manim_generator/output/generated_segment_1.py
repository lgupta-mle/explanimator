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
    Introduce translation example and highlight dependency challenge + long sentences.
    Narration: Imagine you’re using a translation app. You type, “The cat sat on the mat,” and you want fluent German...
    """
    def construct(self):
        # -----------------------------
        # Step 1: Create all shapes
        # -----------------------------
        # Phone UI (rectangle to represent a translation app on the left)
        phone_ui = Rectangle(width=3.2, height=5.6).set_color(GRAY)
        phone_ui.to_edge(LEFT, buff=1.0)

        # Sentences (left side, stacked to the right of the phone frame)
        english_sentence_text = Text("The cat sat on the mat,").scale(0.5).set_color(WHITE)
        german_sentence_text = Text("Die Katze saß auf der Matte.").scale(0.5).set_color(GREEN)
        english_sentence_text.next_to(phone_ui, RIGHT, buff=0.5)
        german_sentence_text.next_to(english_sentence_text, DOWN, buff=0.3)

        # Token highlight boxes for "cat" and "sat"
        token_cat_label = Text("cat").scale(0.45).set_color(WHITE)
        token_cat_rect = Rectangle(width=1.2, height=0.5).set_color(GOLD)
        token_cat_label.move_to(token_cat_rect)
        token_cat_box = VGroup(token_cat_rect, token_cat_label)
        token_cat_box.next_to(english_sentence_text, DOWN, buff=0.8).shift(LEFT * 0.2)

        token_sat_label = Text("sat").scale(0.45).set_color(WHITE)
        token_sat_rect = Rectangle(width=1.2, height=0.5).set_color(GOLD)
        token_sat_label.move_to(token_sat_rect)
        token_sat_box = VGroup(token_sat_rect, token_sat_label)
        token_sat_box.next_to(token_cat_box, RIGHT, buff=1.6)

        # Arrow from cat -> sat (shaft as thin rectangle + triangle head)
        arrow_shaft = Rectangle(width=1.2, height=0.06).set_color(GOLD)
        arrow_shaft.next_to(token_cat_box, RIGHT, buff=0.12)
        arrow_head = Triangle().scale(0.12).set_color(GOLD)
        arrow_head.rotate(-PI / 2)
        arrow_head.next_to(arrow_shaft, RIGHT, buff=0.04)
        arrow_cat_to_sat = VGroup(arrow_shaft, arrow_head)

        # Long sentence timeline (thin rectangle + ticks)
        long_sentence_line = Rectangle(width=8.0, height=0.08).set_color(GRAY)
        long_sentence_line.to_edge(DOWN, buff=1.0)

        # Create 20 ticks as small vertical rectangles, arranged along the timeline
        ticks = VGroup(*[Rectangle(width=0.03, height=0.20).set_color(GRAY) for _ in range(20)])
        ticks.arrange(RIGHT, buff=0.35)
        ticks.move_to(long_sentence_line)
        ticks.next_to(long_sentence_line, UP, buff=0.01)
        long_timeline_group = VGroup(long_sentence_line, ticks)

        # Far link arrow (dashed look: sequence of small horizontal dashes + triangle head)
        dashes = VGroup(*[Rectangle(width=0.28, height=0.06).set_color(ORANGE) for _ in range(12)])
        dashes.arrange(RIGHT, buff=0.10)
        dashes.next_to(long_sentence_line, UP, buff=0.35)
        far_head = Triangle().scale(0.10).set_color(ORANGE)
        far_head.rotate(-PI / 2)
        far_head.next_to(dashes, RIGHT, buff=0.04)
        far_link_arrow = VGroup(dashes, far_head)

        # Challenge label (center)
        challenge_label = Text("Connect who did what — fast, even in long sentences").scale(0.9).set_color(WHITE)
        # Center by default

        # -----------------------------
        # Step 2: Animations in order with timing
        # -----------------------------
        # 1) Fade in phone UI at t=0.0 (run_time=0.8)
        self.play(FadeIn(phone_ui), run_time=0.8)

        # Wait until t=2.4 for the next animation
        self.wait(1.6)

        # 2) Write English input then German output (total run_time=2.2)
        self.play(
            AnimationGroup(
                Write(english_sentence_text),
                Write(german_sentence_text),
                lag_ratio=0.5,
            ),
            run_time=2.2,
        )

        # Wait until t=10.2 for dependency highlight
        self.wait(5.6)

        # 3) Highlight CAT and SAT tokens and draw a linking arrow (run_time=1.5)
        self.play(
            AnimationGroup(
                Create(token_cat_rect),
                Write(token_cat_label),
                Create(token_sat_rect),
                Write(token_sat_label),
                Create(arrow_shaft),
                Create(arrow_head),
                lag_ratio=0.15,
            ),
            run_time=1.5,
        )

        # Wait until t=19.0 for long sentence reveal
        self.wait(7.3)

        # 4) Reveal long sentence timeline, far-distance link, and challenge label (run_time=1.6)
        self.play(
            AnimationGroup(
                FadeIn(long_sentence_line),
                FadeIn(ticks),
                FadeIn(far_link_arrow),
                FadeIn(challenge_label),
                lag_ratio=0.1,
            ),
            run_time=1.6,
        )

        # Hold on screen to reach total segment duration (22.4s)
        self.wait(1.8)


# Scene: scene_2_rnn_limits
class Scene2RnnLimits(Scene):
    """
    Show sequential nature and long-distance weakness of RNN/LSTM.
    Narration: Traditionally, models called RNNs and LSTMs read one word at a time, like a person whispering down a line—accurate but slow, and they struggle to keep track of very long-distance relationships
    """
    def construct(self):
        # ---------- Helpers ----------
        def box_rect(width=0.9, height=0.5, color=RED):
            # Rectangle built from Polygon to stay within demonstrated classes
            hw = width / 2
            hh = height / 2
            return Polygon(
                [-hw, -hh, 0], [hw, -hh, 0], [hw, hh, 0], [-hw, hh, 0],
                color=color
            )

        # ---------- Shapes ----------
        # Label (top-left)
        rnn_label = Text("RNN / LSTM (sequential)", color=RED).scale(0.9)
        rnn_label.move_to(UP * 3 + LEFT * 4)

        # Sequence row: 10 small boxes (center)
        segments = 10
        boxes = VGroup(*[box_rect(color=RED) for _ in range(segments)])
        boxes.arrange(buff=0.15)
        boxes.move_to(ORIGIN)

        # Cursor (circle), starts to the left of the sequence (left)
        rnn_cursor = Circle(color=RED, radius=0.16).scale(0.7)
        rnn_cursor.next_to(boxes[0], LEFT, buff=0.25)

        # Whisper line (dashed, below center)
        whisper_line = DashedLine(
            start=LEFT * 5 + DOWN * 2,
            end=RIGHT * 5 + DOWN * 2,
            color=WHITE
        )

        # Slow clock (top-right), initially hidden (opacity 0)
        clock_circle = Circle(color=WHITE)
        clock_text = Text("⏱")
        slow_clock = VGroup(clock_circle, clock_text)
        slow_clock.scale(0.8)
        slow_clock.move_to(UP * 3 + RIGHT * 4)
        slow_clock.set_opacity(0)

        # Far dependency link (dotted effect using DashedLine + polygon tip)
        # Build from near-left to near-right above the row
        start_point = boxes[1].get_top() + UP * 0.8
        end_point = boxes[-2].get_top() + UP * 0.8
        link_line = DashedLine(start=start_point, end=end_point, color=WHITE)
        # Simple right-pointing triangular arrowhead using Polygon
        arrow_tip = Polygon(
            end_point,
            end_point + LEFT * 0.25 + DOWN * 0.12,
            end_point + LEFT * 0.25 + UP * 0.12,
            color=WHITE
        )
        rnn_far_link = VGroup(link_line, arrow_tip)

        # Add everything to the scene
        self.add(rnn_label, boxes, rnn_cursor, whisper_line, slow_clock, rnn_far_link)

        # ---------- Animations (timed to narration hints) ----------
        # 1) Sequential read: cursor moves across segments (start_time_offset ~ 0.6, duration 5.0)
        self.wait(0.6)
        centers = [b.get_center() for b in boxes]
        per_move = 5.0 / len(centers)  # equal step durations totaling 5.0s
        for c in centers:
            self.play(rnn_cursor.animate.move_to(c), run_time=per_move)

        # 2) Whisper analogy: pulse the dashed line (start_time_offset ~ 3.0, duration 2.0)
        # Use there_and_back color pulse to suggest passing a whisper down the line
        self.play(
            ApplyMethod(whisper_line.set_color, YELLOW),
            rate_func=there_and_back,
            run_time=2.0
        )

        # 3) Show slowness: reveal clock (start_time_offset ~ 6.2, duration 0.8)
        self.play(slow_clock.animate.set_opacity(1), run_time=0.8)

        # 4) Long-distance is hard: dim intermediates, highlight long path (start_time_offset ~ 8.4, duration 2.0)
        # Dim all but two far-apart boxes (keep two highlighted ones undimmed)
        key_a, key_b = 1, 6  # representative far dependency endpoints
        for i, b in enumerate(boxes):
            if i not in (key_a, key_b):
                b.set_color(BLACK)
        # Pulse the far link to highlight the long path
        self.play(
            ApplyMethod(rnn_far_link.set_color, YELLOW),
            rate_func=there_and_back,
            run_time=2.0
        )

        # Hold to complete the segment duration (total ~12.4s)
        self.wait(2.0)


# Scene: scene_3_cnn_steps
class Scene3CnnSteps(Scene):
    """
    Show convolutional windowing and multi-step receptive field growth.
    Narration: Some newer models used convolutions, which can be faster, but still need multiple steps to connect far-apart words
    """
    def construct(self):
        # ---------- Create shapes ----------
        # Label (top-left)
        cnn_label = Text("Convolutions (local windows)", color=PURPLE).scale(0.9)
        cnn_label.to_edge(UP).to_edge(LEFT)

        # Token sequence row (12 small boxes)
        segments = 12
        token_w = 0.7
        token_h = 0.5
        tokens = [Rectangle(width=token_w, height=token_h, color=PURPLE) for _ in range(segments)]
        cnn_sequence_row = VGroup(*tokens).arrange(RIGHT, buff=0.12).move_to(ORIGIN)

        # Convolution kernel window (covers 3 tokens)
        window_size = 3
        first_window_group = VGroup(*tokens[0:window_size])
        mid_start = (segments - window_size) // 2
        middle_window_group = VGroup(*tokens[mid_start:mid_start + window_size])
        last_window_group = VGroup(*tokens[-window_size:])

        # Match the size of the first 3-token span (slight padding for visibility)
        kernel_width = first_window_group.get_width() + 0.06
        kernel_height = first_window_group.get_height() + 0.06
        conv_kernel = Rectangle(width=kernel_width, height=kernel_height, color=PURPLE)
        conv_kernel.move_to(first_window_group.get_center())

        # Stacked conv layers (to the right), revealed later
        layer1 = Rectangle(width=1.6, height=0.35, color=PURPLE)
        layer2 = Rectangle(width=1.6, height=0.35, color=PURPLE)
        layer3 = Rectangle(width=1.6, height=0.35, color=PURPLE)
        cnn_layers_stack = VGroup(layer1, layer2, layer3).arrange(DOWN, buff=0.18).scale(0.9)
        cnn_layers_stack.to_edge(RIGHT)

        # ---------- Add initial objects ----------
        self.add(cnn_label)
        self.add(cnn_sequence_row)
        self.add(conv_kernel)

        # ---------- Animations (timed to narration hints) ----------
        # 0) Initial slight pause before motion (start_time_offset ~ 0.4s)
        self.wait(0.4)

        # 1) Kernel sweeps across the token row (first half toward the middle)
        #    Total requested slide ~3.0s; here we split for timing landmarks.
        self.play(
            conv_kernel.animate.move_to(middle_window_group.get_center()),
            run_time=1.6,
        )

        # 2) Subtle highlight to imply speed (Indicate)
        self.play(Indicate(conv_kernel), run_time=1.0)

        # 3) Reveal stacked layers indicating multi-step connections (at ~3.6s)
        #    Current timeline ~3.0s, wait 0.6s to align with hint, then fade in.
        self.wait(0.6)
        self.play(FadeIn(cnn_layers_stack), run_time=1.2)

        # 4) Continue the kernel sweep to the end of the row
        self.play(
            conv_kernel.animate.move_to(last_window_group.get_center()),
            run_time=1.4,
        )

        # Hold on final frame to reach total segment duration (~7.2s)
        self.wait(1.0)


# Scene: scene_4_transformer_attention
class Scene4TransformerAttention(Scene):
    """
    Introduce Transformer and attention’s all-to-all connectivity.
    Narration: This paper—Attention Is All You Need—introduces the Transformer. Here’s the idea in plain terms: instead of reading word-by-word or using fixed windows, the model uses attention...
    """
    def construct(self):
        import math

        # Layout anchors for split screen
        left_center = LEFT * 3
        right_center = RIGHT * 3

        # 1) Paper title at top
        paper_title = Text("Attention Is All You Need", color=BLACK).scale(1.0)
        paper_title.to_edge(UP)

        # 2) Transformer label slightly below center
        transformer_label = Text("Transformer", color=BLUE).scale(0.9)
        transformer_label.move_to(DOWN * 0.6)

        # 3) Old sequential chain (6 small boxes), placed on the left
        segments = [Rectangle(width=0.6, height=0.35, color=RED) for _ in range(6)]
        old_chain_small = VGroup(*segments).arrange(buff=0.15)
        old_chain_small.scale(0.8)
        old_chain_small.move_to(left_center)
        old_chain_small.set_opacity(1.0)  # will be dimmed later for contrast

        # 4) Attention graph on the right: 6 nodes in a ring, all-to-all connections
        n_nodes = 6
        ring_radius = 1.6
        nodes = []
        positions = []
        for i in range(n_nodes):
            ang = 2 * math.pi * i / n_nodes
            pos = right_center + RIGHT * (ring_radius * math.cos(ang)) + UP * (ring_radius * math.sin(ang))
            node = Circle(color=TEAL, fill_opacity=1).scale(0.12)
            node.move_to(pos)
            nodes.append(node)
            positions.append(pos)
        nodes_group = VGroup(*nodes)

        edges = []
        for i in range(n_nodes):
            for j in range(i + 1, n_nodes):
                p1 = positions[i]
                p2 = positions[j]
                dx = p2[0] - p1[0]
                dy = p2[1] - p1[1]
                length = math.sqrt(dx * dx + dy * dy)
                angle = math.atan2(dy, dx)
                mid = (p1 + p2) / 2
                edge = Rectangle(width=length, height=0.02, fill_opacity=1, color=TEAL)
                edge.set_opacity(0.5)
                edge.rotate(angle)
                edge.move_to(mid)
                edges.append(edge)
        edges_group = VGroup(*edges)
        attention_graph = VGroup(edges_group, nodes_group)

        # 5) Conversation table circle (analogy) and caption (bottom right)
        table_circle = Circle(color=YELLOW, fill_opacity=0.15).scale(0.9)
        table_circle.move_to(right_center)
        attention_caption = Text(
            "Every word can attend to every other, simultaneously",
            color=TEAL
        ).scale(0.8)
        attention_caption.to_edge(DR)

        # Add static elements present before their animations
        self.add(old_chain_small)

        # Timing: follow start_time_offsets precisely with waits
        # 0.0s: Reveal title
        self.play(FadeIn(paper_title), run_time=0.8)

        # 0.8s: Bring in Transformer label
        self.play(FadeIn(transformer_label), run_time=0.8)

        # Wait until 3.2s for contrast highlight
        self.wait(1.6)

        # 3.2s: Dim old chain (set up contrast)
        self.play(old_chain_small.animate.set_opacity(0.2), run_time=2.0)

        # Wait until 6.0s to reveal attention graph
        self.wait(0.8)

        # 6.0s: Reveal all-to-all attention connectivity
        self.play(FadeIn(attention_graph), run_time=3.0)

        # Wait until 12.6s for table analogy
        self.wait(3.6)

        # 12.6s: Show round table and caption
        self.play(FadeIn(table_circle), FadeIn(attention_caption), run_time=2.0)

        # Wait until 16.8s for cross-out
        self.wait(2.2)

        # 16.8s: Cross-out effect on the old chain
        center = old_chain_small.get_center()
        w = old_chain_small.width
        h = old_chain_small.height
        diag = math.sqrt(w * w + h * h)
        cross1 = Rectangle(width=diag, height=0.05, fill_opacity=1, color=RED)
        cross1.move_to(center).rotate(math.radians(45))
        cross2 = Rectangle(width=diag, height=0.05, fill_opacity=1, color=RED)
        cross2.move_to(center).rotate(math.radians(-45))
        self.play(FadeIn(cross1), FadeIn(cross2), run_time=1.6)

        # Hold to complete the segment duration (24.8s total)
        self.wait(6.4)


# Scene: scene_5_why_it_matters
class Scene5WhyItMatters(Scene):
    """
    Motivate with speed, parallelism, long-range capture, and practical gains.
    Narration: Why does this matter? It trains much faster because many operations happen in parallel, and it captures long-range connections better. Practically, that means better translations, more coherent summaries, and smarter assistants—all with shorter training times
    """
    def construct(self):
        # -------------------------
        # Step 1: Create all shapes
        # -------------------------
        # Title
        why_label = Text("Why this matters", color=WHITE).scale(0.9)
        why_label.to_edge(UP)

        # Parallel ops grid (3x5)
        grid_rows = 3
        grid_cols = 5
        cell_size = 0.45
        parallel_cells_rows = []
        for r in range(grid_rows):
            row_cells = VGroup(*[
                Rectangle(width=cell_size, height=cell_size, stroke_color=TEAL_D, fill_color=TEAL_D, fill_opacity=0.25)
                for _ in range(grid_cols)
            ])
            row_cells.arrange(RIGHT, buff=0.15)
            parallel_cells_rows.append(row_cells)
        parallel_ops_grid = VGroup(*parallel_cells_rows)
        parallel_ops_grid.arrange(DOWN, buff=0.15)
        parallel_ops_grid.to_edge(LEFT).shift(UP * 0.5)

        # Speed bar (progress rectangle that grows from ~0% to 100%)
        bar_width_full = 3.6
        bar_height = 0.35
        start_w = 0.02
        speed_bar_start = Rectangle(
            width=start_w,
            height=bar_height,
            stroke_width=0,
            fill_color=GREEN_A,
            fill_opacity=1.0,
        )
        # Place speed bar under the grid
        speed_bar_start.next_to(parallel_ops_grid, DOWN, buff=0.5)
        # Align the small bar's left edge with the left edge of the grid for a neat look
        # Move to the left edge of the grid (approximate by shifting to match left x)
        left_x = parallel_ops_grid.get_left()[0]
        speed_bar_start.move_to(np.array([left_x + start_w / 2.0, speed_bar_start.get_center()[1], 0]))

        # Target (100%) bar for Transform
        speed_bar_full = Rectangle(
            width=bar_width_full,
            height=bar_height,
            stroke_width=0,
            fill_color=GREEN_A,
            fill_opacity=1.0,
        )
        speed_bar_full.move_to(np.array([left_x + bar_width_full / 2.0, speed_bar_start.get_center()[1], 0]))

        # Attention heatmap (6x6) using blue-colored squares with varying opacity
        hm_rows = 6
        hm_cols = 6
        hm_cell = 0.4
        heatmap_rows = []
        heatmap_cells = []  # keep references for highlighting
        for i in range(hm_rows):
            row = []
            row_group = VGroup()
            for j in range(hm_cols):
                # Opacity pattern: higher opacity for farther-from-diagonal cells (long-range)
                dist = abs(i - j)
                opacity = 0.2 + 0.13 * dist  # range roughly 0.2 .. 0.2 + 0.13*5 = 0.85
                sq = Rectangle(
                    width=hm_cell,
                    height=hm_cell,
                    stroke_color=BLUE_E,
                    fill_color=BLUE_E,
                    fill_opacity=min(0.95, opacity),
                )
                row.append(sq)
                row_group.add(sq)
            row_group.arrange(RIGHT, buff=0.06)
            heatmap_rows.append(row_group)
            heatmap_cells.append(row)
        attention_heatmap = VGroup(*heatmap_rows)
        attention_heatmap.arrange(DOWN, buff=0.06)
        attention_heatmap.move_to(ORIGIN)

        # Off-diagonal highlight overlays
        highlight_boxes = VGroup()
        for i in range(hm_rows):
            for j in range(hm_cols):
                if abs(i - j) >= 3:  # emphasize long-range (far off-diagonal)
                    cell = heatmap_cells[i][j]
                    hb = Rectangle(
                        width=hm_cell,
                        height=hm_cell,
                        stroke_color=YELLOW,
                        stroke_width=4,
                        fill_opacity=0,
                    ).move_to(cell.get_center())
                    hb.set_z_index(3)
                    highlight_boxes.add(hb)

        # Practical outcomes (right side)
        outcome_translations = Text("Better translations", color=WHITE).scale(0.8)
        outcome_summaries = Text("More coherent summaries", color=WHITE).scale(0.8)
        outcome_assistants = Text("Smarter assistants", color=WHITE).scale(0.8)
        outcomes = VGroup(
            outcome_translations,
            outcome_summaries,
            outcome_assistants,
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.4)
        outcomes.to_edge(RIGHT).shift(UP * 0.5)

        shorter_time_note = Text("Shorter training times", color=GREEN_A).scale(0.8)
        shorter_time_note.to_edge(DR).shift(LEFT * 0.5 + UP * 0.3)

        # -------------------------
        # Step 2: Initial placements on screen
        # -------------------------
        # Add only elements that should be visible before their animations if needed.
        # We'll keep the grid and heatmap hidden until their FadeIns.
        self.add(why_label)  # Title will be written in, but can be present for timing
        self.remove(why_label)

        # -------------------------
        # Step 3: Animations (timeline with waits to match start_time_offsets)
        # -------------------------
        t = 0.0

        # 0.0s: Write title (0.8s)
        self.play(Write(why_label), run_time=0.8)
        t += 0.8

        # Wait until 1.0s offset for next animations
        if t < 1.0:
            self.wait(1.0 - t)
            t = 1.0

        # 1.0s: Reveal parallel blocks (1.4s) and start speed bar transform (1.2s) simultaneously
        # First, position the speed bar relative to the grid (grid not yet on screen but positioned)
        # Play FadeIn of the grid and Transform growth of the bar at the same time
        self.play(
            FadeIn(parallel_ops_grid, run_time=1.4),
            Transform(speed_bar_start, speed_bar_full, run_time=1.2),
        )
        # The play above lasts 1.4s (max of both)
        t += 1.4

        # 2.6s: Fade in attention heatmap (1.0s)
        if t < 2.6:
            self.wait(2.6 - t)
            t = 2.6
        self.play(FadeIn(attention_heatmap), run_time=1.0)
        t += 1.0  # = 3.6

        # 3.8s: Emphasize off-diagonal (1.2s)
        if t < 3.8:
            self.wait(3.8 - t)
            t = 3.8
        # Bring highlights in
        self.play(FadeIn(highlight_boxes), run_time=1.2)
        t += 1.2  # = 5.0

        # 5.2s: Reveal practical outcomes list (1.4s)
        if t < 5.2:
            self.wait(5.2 - t)
            t = 5.2
        self.play(
            FadeIn(VGroup(outcomes, shorter_time_note)),
            run_time=1.4,
        )
        t += 1.4  # = 6.6

        # -------------------------
        # Step 4: Hold to complete scene duration (14.0s total)
        # -------------------------
        remaining = 14.0 - t
        if remaining > 0:
            self.wait(remaining)


# Scene: scene_6_roadmap
class Scene6Roadmap(Scene):
    """
    Roadmap segment showing upcoming topics and translation example.
    Narration: In this video, we’ll first build the tools to understand attention and self-attention, then we’ll see how the Transformer uses them to turn “The cat sat on the mat” into fluent German
    """
    def construct(self):
        # Helper to create a labeled box (Rectangle + Text)
        def make_box(label_text, color):
            rect = Rectangle(width=4.6, height=1.2, color=color)
            label = Text(label_text)
            box = VGroup(rect, label)
            label.move_to(rect.get_center())
            box.scale(0.9)
            return box

        # Roadmap steps (boxes)
        roadmap_step1 = make_box("Attention basics", TEAL)
        roadmap_step2 = make_box("Self-attention", TEAL)
        roadmap_step3 = make_box("Transformer", BLUE)
        roadmap_step4 = make_box("End-to-end translation example", GREEN)

        # Arrows between steps represented using Text arrows (avoid LaTeX dependency)
        arrow12 = Text("→").set_color(GRAY)
        arrow23 = Text("→").set_color(GRAY)
        arrow34 = Text("→").set_color(GRAY)
        roadmap_arrows = VGroup(arrow12, arrow23, arrow34)

        # Arrange the roadmap chain horizontally and center it
        roadmap_chain = VGroup(
            roadmap_step1,
            arrow12,
            roadmap_step2,
            arrow23,
            roadmap_step3,
            arrow34,
            roadmap_step4,
        ).arrange(RIGHT, buff=0.6).move_to(ORIGIN)

        # Initially hide steps 3 and 4 (they will fade in later)
        roadmap_step3.set_opacity(0)
        roadmap_step4.set_opacity(0)

        # Bottom translation example: English -> German with a bold arrow (Text glyph)
        english_sentence_text = Text("The cat sat on the mat,")
        english_sentence_text.set_color(WHITE).scale(0.9)
        german_sentence_text = Text("Die Katze saß auf der Matte.")
        german_sentence_text.set_color(GREEN).scale(0.9)
        translate_arrow = Text("⇒").set_color(GREEN)

        bottom_chain = VGroup(english_sentence_text, translate_arrow, german_sentence_text)
        bottom_chain.arrange(RIGHT, buff=0.6).to_edge(DOWN)

        # Ensure bottom elements start hidden for later fade-in
        english_sentence_text.set_opacity(0)
        german_sentence_text.set_opacity(0)
        translate_arrow.set_opacity(0)

        # --- Animations ---
        # Align with start_time_offset for first animation
        self.wait(0.2)

        # 1) Reveal first two roadmap steps with connecting arrows (create → FadeIn)
        self.play(
            FadeIn(roadmap_step1),
            FadeIn(roadmap_step2),
            FadeIn(roadmap_arrows),
            run_time=1.2,
        )

        # Wait until next start_time_offset (3.2s from segment start)
        self.wait(1.8)

        # 2) Bring in Transformer step
        self.play(FadeIn(roadmap_step3), run_time=0.8)

        # Wait until next start_time_offset (5.4s from segment start)
        self.wait(1.4)

        # 3) Reveal final step and show planned translation path
        self.play(
            FadeIn(roadmap_step4),
            FadeIn(english_sentence_text),
            FadeIn(german_sentence_text),
            FadeIn(translate_arrow),
            run_time=1.6,
        )

        # Hold the final view for the remaining duration of the segment
        self.wait(5.8)


