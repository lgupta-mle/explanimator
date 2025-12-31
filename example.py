from manim import *

class CreateCircle(Scene):
    def construct(self):
        circle = Circle()  # create a circle
        circle.set_fill(PINK, opacity=0.5)  # set the color and transparency
        self.play(Create(circle))  # show the circle on screen

class SquareToCircle(Scene):
    def construct(self):
        square = Square()
        circle = Circle() 
        self.play(Create(square))
        self.play(Transform(square, circle))
        self.play(FadeOut(square))