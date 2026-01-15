"""
Generated Manim Animation: Attention Is All You Need

3Blue1Brown-style educational video animation.
Generated from PDF using pdf_to_manim_pipeline.

To render a scene:
    manim -pql generated_animation.py <ClassName>

To render all:
    manim -pql generated_animation.py -a
"""

from manim import *
import numpy as np



# ======================================================================
# Scene: seg1
# ======================================================================

from manim import *

class TransformerAttentionVisualization(Scene):
    """Visualizes the attention mechanism in Transformers with words as points on a circle."""
    
    def construct(self):
        # Title
        title = Text("The Heart of the Transformer", font_size=48)
        title.to_edge(UP)
        self.play(Write(title), run_time=1.5)
        self.wait(0.5)
        
        # Sample sentence words
        words = ["The", "law", "will", "never", "be", "perfect", "but", "its"]
        num_words = len(words)
        
        # Create dots arranged in a circle
        radius = 2.5
        dots = VGroup()
        labels = VGroup()
        
        for i, word in enumerate(words):
            angle = 2 * PI * i / num_words - PI/2
            pos = radius * np.array([np.cos(angle), np.sin(angle), 0])
            dot = Dot(point=pos, color=BLUE, radius=0.12)
            label = Text(word, font_size=24)
            label.next_to(dot, pos/np.linalg.norm(pos) * 0.5)
            dots.add(dot)
            labels.add(label)
        
        self.play(Create(dots), run_time=1.5)
        self.play(FadeIn(labels, shift=UP*0.2), run_time=1.0)
        self.wait(0.5)
        
        # Create faint connection lines between all pairs
        connections = VGroup()
        for i in range(num_words):
            for j in range(i+1, num_words):
                line = Line(dots[i].get_center(), dots[j].get_center(), stroke_width=0.5, stroke_opacity=0.2, color=GRAY)
                connections.add(line)
        
        self.play(Create(connections), run_time=2.0)
        self.wait(0.5)
        
        # Highlight 'its' and 'law' connection
        its_idx = 7
        law_idx = 1
        highlight_line = Line(dots[its_idx].get_center(), dots[law_idx].get_center(), stroke_width=4, color=YELLOW)
        
        self.play(dots[its_idx].animate.set_color(YELLOW), dots[law_idx].animate.set_color(YELLOW), run_time=0.8)
        self.play(Create(highlight_line), run_time=1.0)
        self.wait(0.5)
        
        self.play(FadeOut(highlight_line), dots[its_idx].animate.set_color(BLUE), dots[law_idx].animate.set_color(BLUE), run_time=0.5)
        
        # Show multiple attention heads with different colors
        head_colors = [RED, GREEN, ORANGE]
        head_lines = VGroup()
        
        for color in head_colors:
            line = Line(dots[0].get_center(), dots[2].get_center(), stroke_width=2, color=color)
            head_lines.add(line)
        
        self.play(Create(head_lines), run_time=1.5)
        self.wait(0.5)
        self.play(FadeOut(head_lines), FadeOut(connections), run_time=0.8)
        
        # Show attention equation
        equation = MathTex(
            r"\text{Attention}(Q, K, V) = \text{softmax}\left(\frac{QK^\top}{\sqrt{d_k}}\right) V",
            font_size=36
        )
        equation.to_edge(DOWN)
        
        self.play(Write(equation), run_time=2.0)
        self.wait(1.0)
        
        # Show weighted movement of a dot
        arrow = Arrow(dots[its_idx].get_center(), dots[law_idx].get_center(), buff=0.1, color=YELLOW, stroke_width=3)
        self.play(Create(arrow), run_time=1.0)
        self.play(dots[its_idx].animate.shift((dots[law_idx].get_center() - dots[its_idx].get_center()) * 0.2), run_time=1.5)
        self.wait(0.5)
        
        # Show residual connection equation
        residual_eq = MathTex(
            r"y = \text{LayerNorm}(x + \text{Sublayer}(x))",
            font_size=36
        )
        residual_eq.next_to(equation, UP, buff=0.5)
        
        self.play(FadeOut(arrow), run_time=0.5)
        self.play(Write(residual_eq), run_time=1.5)
        self.wait(1.0)
        
        # Final wait
        self.wait(2.0)




# ======================================================================
# Scene: seg3
# ======================================================================

from manim import *

class ScaledDotProductAttentionScene(Scene):
    """Visualizes scaled dot-product attention and multi-head mechanism. Shows Q/K/V projections, attention heatmap for 'its', and parallel multi-head streams."""
    
    def construct(self):
        # Title
        title = Text("Scaled Dot-Product & Multi-Head Attention", font_size=36)
        title.to_edge(UP)
        self.play(Write(title), run_time=1.0)
        self.wait(0.5)
        
        # Step 1: Show Q, K, V projections from token vector
        token_label = Text("Token: 'its'", font_size=28, color=WHITE)
        token_label.shift(LEFT * 4 + UP * 1.5)
        token_arrow = Arrow(start=ORIGIN, end=RIGHT * 1.5, color=WHITE, buff=0)
        token_arrow.next_to(token_label, DOWN, buff=0.3)
        
        self.play(FadeIn(token_label), Create(token_arrow), run_time=1.0)
        self.wait(0.3)
        
        # Create Q, K, V arrows
        q_arrow = Arrow(start=ORIGIN, end=RIGHT * 1.5, color=BLUE, buff=0)
        k_arrow = Arrow(start=ORIGIN, end=RIGHT * 1.5, color=GREEN, buff=0)
        v_arrow = Arrow(start=ORIGIN, end=RIGHT * 1.5, color=ORANGE, buff=0)
        
        q_arrow.shift(RIGHT * 0.5 + UP * 0.5)
        k_arrow.shift(RIGHT * 0.5)
        v_arrow.shift(RIGHT * 0.5 + DOWN * 0.5)
        
        q_label = MathTex("Q", color=BLUE, font_size=32).next_to(q_arrow, RIGHT, buff=0.2)
        k_label = MathTex("K", color=GREEN, font_size=32).next_to(k_arrow, RIGHT, buff=0.2)
        v_label = MathTex("V", color=ORANGE, font_size=32).next_to(v_arrow, RIGHT, buff=0.2)
        
        qkv_group = VGroup(q_arrow, k_arrow, v_arrow, q_label, k_label, v_label)
        
        self.play(
            Transform(token_arrow.copy(), q_arrow),
            Transform(token_arrow.copy(), k_arrow),
            Transform(token_arrow.copy(), v_arrow),
            Write(q_label), Write(k_label), Write(v_label),
            run_time=1.5
        )
        self.wait(0.5)
        
        # Show projection equation
        proj_eq = MathTex(
            "Q = X W^Q,\\quad K = X W^K,\\quad V = X W^V",
            font_size=32
        )
        proj_eq.shift(DOWN * 2.5)
        self.play(Write(proj_eq), run_time=1.5)
        self.wait(0.5)
        
        # Clear for attention heatmap
        self.play(
            FadeOut(token_label), FadeOut(token_arrow),
            FadeOut(qkv_group), FadeOut(proj_eq),
            run_time=0.8
        )
        
        # Step 2: Attention heatmap
        tokens = ["The", "law", "will", "never", "be", "its"]
        token_labels = VGroup(*[Text(t, font_size=24) for t in tokens])
        token_labels.arrange(RIGHT, buff=0.4)
        token_labels.shift(UP * 2)
        
        self.play(FadeIn(token_labels), run_time=1.0)
        
        # Create heatmap grid (query 'its' vs all keys)
        grid_size = 0.5
        heatmap_cells = VGroup()
        attention_weights = [0.1, 0.5, 0.05, 0.05, 0.05, 0.25]  # 'its' attends to 'law' and itself
        
        for i, weight in enumerate(attention_weights):
            cell = Square(side_length=grid_size)
            cell.set_fill(BLUE, opacity=weight * 1.5)
            cell.set_stroke(WHITE, width=1)
            cell.shift(LEFT * 2 + RIGHT * i * grid_size + UP * 0.5)
            heatmap_cells.add(cell)
        
        query_label = Text("Q: 'its'", font_size=24, color=BLUE)
        query_label.next_to(heatmap_cells, LEFT, buff=0.5)
        
        self.play(
            Create(heatmap_cells),
            FadeIn(query_label),
            run_time=1.5
        )
        self.wait(0.5)
        
        # Show attention equation
        attn_eq = MathTex(
            "\\mathrm{Attention}(Q,K,V) = \\operatorname{softmax}\\!\\left(\\frac{QK^\\top}{\\sqrt{d_k}}\\right) V",
            font_size=28
        )
        attn_eq.shift(DOWN * 1.5)
        self.play(Write(attn_eq), run_time=2.0)
        self.wait(0.5)
        
        # Clear for multi-head
        self.play(
            FadeOut(token_labels), FadeOut(heatmap_cells),
            FadeOut(query_label), FadeOut(attn_eq),
            run_time=0.8
        )
        
        # Step 3: Multi-head attention
        head_label = Text("Multi-Head Attention", font_size=32)
        head_label.shift(UP * 2.5)
        self.play(Write(head_label), run_time=1.0)
        
        # Create 3 parallel attention heads with different colors
        head_colors = [RED, PURPLE, TEAL]
        head_groups = VGroup()
        
        for i, color in enumerate(head_colors):
            head_rect = Rectangle(width=1.5, height=2.5, color=color)
            head_rect.shift(LEFT * 3 + RIGHT * i * 2.5 + DOWN * 0.5)
            head_text = Text(f"Head {i+1}", font_size=20, color=color)
            head_text.next_to(head_rect, UP, buff=0.2)
            
            # Mini heatmap inside each head
            mini_grid = VGroup()
            for j in range(4):
                mini_cell = Square(side_length=0.25)
                mini_cell.set_fill(color, opacity=0.3 + (i + j) * 0.1)
                mini_cell.set_stroke(color, width=0.5)
                mini_cell.move_to(head_rect.get_center() + UP * 0.4 + LEFT * 0.4 + RIGHT * j * 0.25)
                mini_grid.add(mini_cell)
            
            head_group = VGroup(head_rect, head_text, mini_grid)
            head_groups.add(head_group)
        
        self.play(Create(head_groups), run_time=2.0)
        self.wait(0.5)
        
        # Show concatenation
        concat_arrow = Arrow(start=DOWN * 0.5, end=DOWN * 2, color=YELLOW, buff=0.1)
        concat_arrow.shift(RIGHT * 0.5)
        concat_label = Text("Concat + Mix", font_size=24, color=YELLOW)
        concat_label.next_to(concat_arrow, RIGHT, buff=0.3)
        
        output_rect = Rectangle(width=2, height=0.8, color=YELLOW)
        output_rect.shift(DOWN * 2.5)
        output_text = Text("Output", font_size=20, color=YELLOW)
        output_text.move_to(output_rect.get_center())
        
        self.play(
            Create(concat_arrow),
            FadeIn(concat_label),
            Create(output_rect),
            Write(output_text),
            run_time=1.5
        )
        self.wait(0.5)
        
        # Final equation
        multi_eq = MathTex(
            "\\mathrm{MultiHead}(Q,K,V) = \\mathrm{Concat}(\\mathrm{head}_1,\\ldots,\\mathrm{head}_h) W^O",
            font_size=26
        )
        multi_eq.to_edge(DOWN, buff=0.5)
        self.play(Write(multi_eq), run_time=2.0)
        self.wait(2.0)
        
        # Fade all
        self.play(
            *[FadeOut(mob) for mob in self.mobjects],
            run_time=1.0
        )
        self.wait(0.5)



# ======================================================================
# Scene: seg4
# ======================================================================

from manim import *

class EncoderDecoderArchitecture(Scene):
    """Transformer encoder-decoder architecture with masked attention, residuals, and cross-attention. Narration: Build the encoder as a stack: multi-head self-attention spreads information globally, then a small per..."""
    def construct(self):
        # Title
        title = Text("Encoder-Decoder Architecture", font_size=36).to_edge(UP)
        self.play(Write(title), run_time=1.0)
        self.wait(0.5)
        
        # Step 1: Create encoder block structure
        enc_box = Rectangle(width=3.5, height=5, color=BLUE).shift(LEFT * 4)
        enc_label = Text("Encoder", font_size=28, color=BLUE).next_to(enc_box, UP, buff=0.2)
        
        # Encoder components
        enc_attn = Rectangle(width=3, height=1.2, color=GREEN, fill_opacity=0.3).move_to(enc_box.get_center() + UP * 1.5)
        enc_attn_text = Text("Self-Attn", font_size=20).move_to(enc_attn.get_center())
        
        enc_ffn = Rectangle(width=3, height=1.2, color=ORANGE, fill_opacity=0.3).move_to(enc_box.get_center() + DOWN * 1.5)
        enc_ffn_text = Text("FFN", font_size=20).move_to(enc_ffn.get_center())
        
        # Residual connections
        enc_res1 = Arrow(start=enc_attn.get_left() + LEFT * 0.3, end=enc_attn.get_right() + DOWN * 1.5 + RIGHT * 0.3, color=YELLOW, buff=0.1, stroke_width=3)
        enc_res2 = Arrow(start=enc_ffn.get_left() + LEFT * 0.3, end=enc_ffn.get_right() + DOWN * 1.5 + RIGHT * 0.3, color=YELLOW, buff=0.1, stroke_width=3)
        
        encoder_group = VGroup(enc_box, enc_label, enc_attn, enc_attn_text, enc_ffn, enc_ffn_text)
        
        self.play(Create(enc_box), Write(enc_label), run_time=1.0)
        self.play(FadeIn(enc_attn), Write(enc_attn_text), run_time=0.8)
        self.play(Create(enc_res1), run_time=0.6)
        self.play(FadeIn(enc_ffn), Write(enc_ffn_text), run_time=0.8)
        self.play(Create(enc_res2), run_time=0.6)
        self.wait(0.5)
        
        # Step 2: Create decoder block structure
        dec_box = Rectangle(width=3.5, height=6.5, color=RED).shift(RIGHT * 4)
        dec_label = Text("Decoder", font_size=28, color=RED).next_to(dec_box, UP, buff=0.2)
        
        # Decoder components
        dec_masked_attn = Rectangle(width=3, height=1.0, color=PURPLE, fill_opacity=0.3).move_to(dec_box.get_center() + UP * 2.2)
        dec_masked_text = Text("Masked\nSelf-Attn", font_size=18).move_to(dec_masked_attn.get_center())
        
        dec_cross_attn = Rectangle(width=3, height=1.0, color=TEAL, fill_opacity=0.3).move_to(dec_box.get_center() + UP * 0.5)
        dec_cross_text = Text("Cross-Attn", font_size=18).move_to(dec_cross_attn.get_center())
        
        dec_ffn = Rectangle(width=3, height=1.0, color=ORANGE, fill_opacity=0.3).move_to(dec_box.get_center() + DOWN * 1.2)
        dec_ffn_text = Text("FFN", font_size=20).move_to(dec_ffn.get_center())
        
        dec_softmax = Rectangle(width=3, height=0.8, color=GOLD, fill_opacity=0.3).move_to(dec_box.get_center() + DOWN * 2.5)
        dec_softmax_text = Text("Softmax", font_size=18).move_to(dec_softmax.get_center())
        
        decoder_group = VGroup(dec_box, dec_label, dec_masked_attn, dec_masked_text, dec_cross_attn, dec_cross_text, dec_ffn, dec_ffn_text, dec_softmax, dec_softmax_text)
        
        self.play(Create(dec_box), Write(dec_label), run_time=1.0)
        self.play(FadeIn(dec_masked_attn), Write(dec_masked_text), run_time=0.8)
        self.wait(0.3)
        
        # Step 3: Show causal mask visualization
        mask_matrix = Matrix([["1", "0", "0"], ["1", "1", "0"], ["1", "1", "1"]], h_buff=1.2).scale(0.6).next_to(dec_masked_attn, RIGHT, buff=1.5)
        mask_label = Text("Causal\nMask", font_size=18).next_to(mask_matrix, UP, buff=0.2)
        
        self.play(Create(mask_matrix), Write(mask_label), run_time=1.0)
        self.play(Indicate(mask_matrix), run_time=0.8)
        self.wait(0.3)
        self.play(FadeOut(mask_matrix), FadeOut(mask_label), run_time=0.5)
        
        # Step 4: Cross-attention bridge
        self.play(FadeIn(dec_cross_attn), Write(dec_cross_text), run_time=0.8)
        cross_arrows = VGroup(
            Arrow(start=enc_box.get_right(), end=dec_cross_attn.get_left(), color=TEAL, buff=0.1),
            Arrow(start=enc_box.get_right() + UP * 0.3, end=dec_cross_attn.get_left() + UP * 0.2, color=TEAL, buff=0.1),
            Arrow(start=enc_box.get_right() + DOWN * 0.3, end=dec_cross_attn.get_left() + DOWN * 0.2, color=TEAL, buff=0.1)
        )
        self.play(Create(cross_arrows), run_time=1.2)
        self.wait(0.5)
        
        # Step 5: Complete decoder with FFN and softmax
        self.play(FadeIn(dec_ffn), Write(dec_ffn_text), run_time=0.8)
        self.play(FadeIn(dec_softmax), Write(dec_softmax_text), run_time=0.8)
        self.wait(0.5)
        
        # Step 6: Show key equations
        eq1 = MathTex(r"Y_{enc}^{(\ell)} = \mathrm{LN}(X + \mathrm{MHA}(X))", font_size=32).to_edge(DOWN).shift(UP * 0.5)
        self.play(Write(eq1), run_time=1.5)
        self.wait(1.0)
        
        eq2 = MathTex(r"A_{mask} = \mathrm{softmax}\left(\frac{QK^\top + M}{\sqrt{d_k}}\right)", font_size=32).move_to(eq1.get_center())
        self.play(Transform(eq1, eq2), run_time=1.0)
        self.wait(1.0)
        
        eq3 = MathTex(r"Z = \mathrm{MHA}(Q_{dec}, K_{enc}, V_{enc})", font_size=32).move_to(eq1.get_center())
        self.play(Transform(eq1, eq3), run_time=1.0)
        self.wait(1.0)
        
        # Final highlighting
        self.play(
            Indicate(encoder_group, scale_factor=1.05, color=BLUE),
            Indicate(decoder_group, scale_factor=1.05, color=RED),
            run_time=1.5
        )
        self.wait(2.0)



# ======================================================================
# Scene: seg5
# ======================================================================

from manim import *

class AttentionVsRNNPathLength(Scene):
    """
    Visualizes the contrast between RNN sequential processing (corridor with doors)
    and attention parallel processing (courtyard with all-to-all connections).
    Shows path length differences and computational complexity.
    Narration: Contrast a corridor with doors—an RNN—with a courtyard where anyone...
    """
    def construct(self):
        # Title
        title = Text("Why Attention Is Special", font_size=40)
        title.to_edge(UP)
        self.play(Write(title), run_time=1.0)
        self.wait(0.5)
        
        # Step 1: Create RNN corridor visualization (left side)
        rnn_label = Text("RNN: Corridor", font_size=28, color=RED)
        rnn_label.move_to(LEFT * 4.5 + UP * 2)
        
        # Create corridor with doors
        corridor_rects = VGroup(*[
            Rectangle(width=0.6, height=0.6, color=RED, fill_opacity=0.3)
            for _ in range(5)
        ]).arrange(RIGHT, buff=0.3)
        corridor_rects.move_to(LEFT * 4 + UP * 0.5)
        
        # Arrows showing sequential path
        corridor_arrows = VGroup(*[
            Arrow(corridor_rects[i].get_right(), corridor_rects[i+1].get_left(), 
                  buff=0.05, color=RED, stroke_width=3)
            for i in range(4)
        ])
        
        rnn_group = VGroup(rnn_label, corridor_rects, corridor_arrows)
        
        # Step 2: Create Attention courtyard visualization (right side)
        attn_label = Text("Attention: Courtyard", font_size=28, color=BLUE)
        attn_label.move_to(RIGHT * 4 + UP * 2)
        
        # Create nodes in circular arrangement
        courtyard_nodes = VGroup(*[
            Circle(radius=0.25, color=BLUE, fill_opacity=0.5)
            for _ in range(5)
        ]).arrange_in_grid(rows=1, cols=5, buff=0.8)
        courtyard_nodes.move_to(RIGHT * 4 + UP * 0.5)
        
        # Create all-to-all connections
        courtyard_connections = VGroup()
        for i in range(5):
            for j in range(i+1, 5):
                line = Line(courtyard_nodes[i].get_center(), 
                           courtyard_nodes[j].get_center(),
                           color=BLUE, stroke_width=1.5, stroke_opacity=0.4)
                courtyard_connections.add(line)
        
        attn_group = VGroup(attn_label, courtyard_connections, courtyard_nodes)
        
        # Animate RNN corridor
        self.play(FadeIn(rnn_label), run_time=0.8)
        self.play(Create(corridor_rects), run_time=1.2)
        self.play(Create(corridor_arrows), run_time=1.0)
        self.wait(0.5)
        
        # Animate attention courtyard
        self.play(FadeIn(attn_label), run_time=0.8)
        self.play(Create(courtyard_nodes), run_time=1.0)
        self.play(Create(courtyard_connections), run_time=1.5)
        self.wait(1.0)
        
        # Step 3: Highlight path length difference
        # Show path from first to last node in RNN (many hops)
        rnn_path_label = Text("Path: O(n) hops", font_size=20, color=RED)
        rnn_path_label.next_to(corridor_rects, DOWN, buff=0.5)
        
        # Highlight sequential path
        path_highlight = AnimationGroup(*[
            Indicate(corridor_rects[i], color=YELLOW, scale_factor=1.3)
            for i in range(5)
        ], lag_ratio=0.3)
        
        self.play(Write(rnn_path_label), run_time=0.8)
        self.play(path_highlight, run_time=2.0)
        self.wait(0.5)
        
        # Show direct path in attention (single hop)
        attn_path_label = Text("Path: O(1) hop", font_size=20, color=BLUE)
        attn_path_label.next_to(courtyard_nodes, DOWN, buff=0.5)
        
        direct_line = Line(courtyard_nodes[0].get_center(),
                          courtyard_nodes[4].get_center(),
                          color=YELLOW, stroke_width=6)
        
        self.play(Write(attn_path_label), run_time=0.8)
        self.play(Create(direct_line), run_time=1.0)
        self.play(FadeOut(direct_line), run_time=0.5)
        self.wait(1.0)
        
        # Step 4: Show complexity equations
        self.play(FadeOut(rnn_group), FadeOut(attn_group), 
                 FadeOut(rnn_path_label), FadeOut(attn_path_label),
                 run_time=1.0)
        
        # Complexity comparison
        complexity_title = Text("Computational Complexity", font_size=32)
        complexity_title.move_to(UP * 2.5)
        
        rnn_complexity = MathTex(
            r"\text{RNN: } \mathcal{O}(n d^2),\ \text{depth } \mathcal{O}(n)",
            font_size=36, color=RED
        ).move_to(UP * 1)
        
        attn_complexity = MathTex(
            r"\text{Attention: } \mathcal{O}(n^2 d),\ \text{depth } \mathcal{O}(1)",
            font_size=36, color=BLUE
        ).move_to(ORIGIN)
        
        parallel_note = Text(
            "Parallel hardware excels at attention's matrix multiplies",
            font_size=24, color=GREEN
        ).move_to(DOWN * 1.5)
        
        self.play(Write(complexity_title), run_time=1.0)
        self.wait(0.3)
        self.play(Write(rnn_complexity), run_time=1.5)
        self.wait(0.5)
        self.play(Write(attn_complexity), run_time=1.5)
        self.wait(0.5)
        self.play(FadeIn(parallel_note), run_time=1.2)
        self.wait(2.0)
        
        # Step 5: Multi-head specialization visualization
        self.play(FadeOut(complexity_title), FadeOut(rnn_complexity),
                 FadeOut(attn_complexity), FadeOut(parallel_note),
                 run_time=1.0)
        
        multihead_title = Text("Multi-Head Specialization", font_size=36)
        multihead_title.to_edge(UP)
        
        # Create three attention heads with different patterns
        head_colors = [RED, GREEN, BLUE]
        heads = VGroup()
        
        for i, color in enumerate(head_colors):
            head_label = Text(f"Head {i+1}", font_size=20, color=color)
            head_label.move_to(LEFT * 4 + RIGHT * i * 3.5 + UP * 1.5)
            
            # Small grid representing attention pattern
            grid = VGroup(*[
                Square(side_length=0.3, color=color, fill_opacity=0.6)
                for _ in range(9)
            ]).arrange_in_grid(rows=3, cols=3, buff=0.1)
            grid.move_to(LEFT * 4 + RIGHT * i * 3.5 + DOWN * 0.3)
            
            heads.add(VGroup(head_label, grid))
        
        self.play(Write(multihead_title), run_time=1.0)
        self.play(FadeIn(heads), run_time=1.5)
        self.wait(2.0)
        
        # Final message
        final_message = Text(
            "Short paths + Parallelism = Speed + Long-range understanding",
            font_size=28, color=YELLOW
        ).move_to(DOWN * 2.5)
        
        self.play(Write(final_message), run_time=2.0)
        self.wait(3.0)



# ======================================================================
# Scene: seg6
# ======================================================================

from manim import *
import numpy as np

class TrainingAndBigPictureScene(Scene):
    """
    Visualizes transformer training techniques: learning rate schedule, dropout,
    weight tying, and beam search inference.
    Narration: To train, turn the learning rate up gently, then let it decay...
    """
    def construct(self):
        # Title
        title = Text("Training & The Big Picture", font_size=48)
        title.to_edge(UP)
        self.play(Write(title), run_time=1.0)
        self.wait(0.5)
        
        # Section 1: Learning Rate Schedule
        lr_title = Text("Learning Rate Schedule", font_size=36, color=BLUE)
        lr_title.next_to(title, DOWN, buff=0.8)
        
        # Learning rate equation
        lr_equation = MathTex(
            r"\text{lrate} = d_{model}^{-1/2} \cdot \min(\text{step}^{-1/2}, \text{step} \cdot \text{warmup}^{-3/2})",
            font_size=32
        )
        lr_equation.next_to(lr_title, DOWN, buff=0.5)
        
        # Create axes for learning rate curve
        axes = Axes(
            x_range=[0, 10, 2],
            y_range=[0, 1.2, 0.4],
            x_length=5,
            y_length=2.5,
            axis_config={"color": GRAY},
            tips=False
        )
        axes.next_to(lr_equation, DOWN, buff=0.5)
        
        x_label = Text("step", font_size=24).next_to(axes.x_axis, RIGHT)
        y_label = Text("lrate", font_size=24).next_to(axes.y_axis, UP)
        
        # Learning rate curve (warmup then decay)
        def lr_func(x):
            warmup_steps = 2.0
            if x < warmup_steps:
                return x / warmup_steps
            else:
                return 1.0 / np.sqrt(x / warmup_steps)
        
        lr_curve = axes.plot(lr_func, x_range=[0.1, 10], color=YELLOW)
        
        self.play(FadeIn(lr_title), run_time=0.8)
        self.play(Write(lr_equation), run_time=1.5)
        self.play(Create(axes), Write(x_label), Write(y_label), run_time=1.0)
        self.play(Create(lr_curve), run_time=2.0)
        self.wait(1.0)
        
        # Clear for next section
        self.play(
            FadeOut(lr_title),
            FadeOut(lr_equation),
            FadeOut(axes),
            FadeOut(x_label),
            FadeOut(y_label),
            FadeOut(lr_curve),
            run_time=0.8
        )
        
        # Section 2: Dropout Visualization
        dropout_title = Text("Dropout Regularization", font_size=36, color=GREEN)
        dropout_title.next_to(title, DOWN, buff=0.8)
        
        # Create a simple network with connections
        layer1 = VGroup(*[Circle(radius=0.15, color=BLUE, fill_opacity=0.8) for _ in range(4)])
        layer1.arrange(DOWN, buff=0.4)
        layer1.shift(LEFT * 2)
        
        layer2 = VGroup(*[Circle(radius=0.15, color=BLUE, fill_opacity=0.8) for _ in range(4)])
        layer2.arrange(DOWN, buff=0.4)
        layer2.shift(RIGHT * 2)
        
        # Create connections
        connections = VGroup()
        for n1 in layer1:
            for n2 in layer2:
                line = Line(n1.get_center(), n2.get_center(), stroke_width=1, color=WHITE, stroke_opacity=0.3)
                connections.add(line)
        
        network = VGroup(connections, layer1, layer2)
        network.scale(0.8)
        network.next_to(dropout_title, DOWN, buff=0.6)
        
        self.play(FadeIn(dropout_title), run_time=0.8)
        self.play(Create(layer1), Create(layer2), run_time=1.0)
        self.play(Create(connections), run_time=1.0)
        
        # Animate dropout: randomly fade out some connections
        dropout_mask = [0, 2, 5, 7, 10, 13]  # indices to fade
        dropout_lines = VGroup(*[connections[i] for i in dropout_mask])
        
        self.play(dropout_lines.animate.set_opacity(0.05), run_time=0.8)
        self.wait(0.5)
        self.play(dropout_lines.animate.set_opacity(0.3), run_time=0.8)
        self.wait(0.5)
        
        # Clear for next section
        self.play(
            FadeOut(dropout_title),
            FadeOut(network),
            run_time=0.8
        )
        
        # Section 3: Weight Tying and Label Smoothing
        weight_title = Text("Weight Tying & Label Smoothing", font_size=36, color=ORANGE)
        weight_title.next_to(title, DOWN, buff=0.8)
        
        # Weight tying equation
        weight_eq = MathTex(
            r"W_{emb}^{in} = W_{emb}^{out\top}",
            font_size=36
        )
        weight_eq.next_to(weight_title, DOWN, buff=0.5)
        
        # Label smoothing equation
        ls_eq = MathTex(
            r"L_{ls} = -(1-\epsilon)\log p(y^*) - \sum_{y\ne y^*} \frac{\epsilon}{V-1} \log p(y)",
            font_size=28
        )
        ls_eq.next_to(weight_eq, DOWN, buff=0.5)
        
        # Visual: shared matrix
        matrix_box = Rectangle(width=1.5, height=2, color=PURPLE, fill_opacity=0.3)
        matrix_box.shift(LEFT * 2.5 + DOWN * 0.5)
        matrix_label = Text("Shared\nWeights", font_size=24).move_to(matrix_box.get_center())
        
        input_arrow = Arrow(matrix_box.get_left(), matrix_box.get_left() + LEFT * 1.5, color=YELLOW)
        input_label = Text("Input\nEmbed", font_size=20).next_to(input_arrow, LEFT, buff=0.2)
        
        output_arrow = Arrow(matrix_box.get_right(), matrix_box.get_right() + RIGHT * 1.5, color=YELLOW)
        output_label = Text("Output\nLogits", font_size=20).next_to(output_arrow, RIGHT, buff=0.2)
        
        weight_visual = VGroup(matrix_box, matrix_label, input_arrow, input_label, output_arrow, output_label)
        weight_visual.shift(DOWN * 1.5)
        
        self.play(FadeIn(weight_title), run_time=0.8)
        self.play(Write(weight_eq), run_time=1.2)
        self.play(Write(ls_eq), run_time=1.5)
        self.play(Create(weight_visual), run_time=1.5)
        self.wait(1.0)
        
        # Clear for final section
        self.play(
            FadeOut(weight_title),
            FadeOut(weight_eq),
            FadeOut(ls_eq),
            FadeOut(weight_visual),
            run_time=0.8
        )
        
        # Section 4: Beam Search
        beam_title = Text("Beam Search Inference", font_size=36, color=RED)
        beam_title.next_to(title, DOWN, buff=0.8)
        
        # Create a simple beam search tree
        root = Circle(radius=0.2, color=WHITE, fill_opacity=0.8)
        root.move_to(UP * 0.5 + LEFT * 3)
        
        # Level 1: 3 candidates
        level1 = VGroup(*[Circle(radius=0.15, color=BLUE, fill_opacity=0.6) for _ in range(3)])
        level1.arrange(DOWN, buff=0.5)
        level1.next_to(root, RIGHT, buff=1.5)
        
        lines1 = VGroup(*[Line(root.get_center(), n.get_center(), color=GRAY) for n in level1])
        
        # Level 2: Keep top 2 beams
        level2 = VGroup(*[Circle(radius=0.15, color=GREEN, fill_opacity=0.6) for _ in range(2)])
        level2.arrange(DOWN, buff=0.8)
        level2.next_to(level1, RIGHT, buff=1.5)
        level2.shift(UP * 0.3)
        
        lines2 = VGroup(
            Line(level1[0].get_center(), level2[0].get_center(), color=GRAY),
            Line(level1[1].get_center(), level2[1].get_center(), color=GRAY)
        )
        
        # Final choice
        final = Circle(radius=0.2, color=YELLOW, fill_opacity=0.8)
        final.next_to(level2, RIGHT, buff=1.5)
        final.shift(DOWN * 0.2)
        
        line_final = Line(level2[0].get_center(), final.get_center(), color=YELLOW, stroke_width=3)
        
        beam_tree = VGroup(root, lines1, level1, lines2, level2, line_final, final)
        beam_tree.scale(0.9)
        beam_tree.shift(DOWN * 0.8)
        
        self.play(FadeIn(beam_title), run_time=0.8)
        self.play(Create(root), run_time=0.5)
        self.play(Create(lines1), Create(level1), run_time=1.0)
        self.play(Create(lines2), Create(level2), run_time=1.0)
        self.play(Create(line_final), Create(final), run_time=1.0)
        self.wait(1.0)
        
        # Final message
        final_text = Text("Clean translation with long-range dependencies!", font_size=28, color=GREEN)
        final_text.to_edge(DOWN, buff=0.5)
        self.play(FadeIn(final_text), run_time=1.0)
        self.wait(2.0)
        
        # Fade out everything
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=1.0)

