import tkinter as tk
from PIL import Image, ImageTk, ImageSequence
import random


class DesktopPet:
    def __init__(self, root):
        self.root = root
        self.state = "walking"

        # Configuración ventana
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.wm_attributes("-transparentcolor", "white")

        # Cargar GIF
        self.gif = Image.open("rana.gif")
        self.frames = [
            ImageTk.PhotoImage(frame.copy().convert("RGBA"))
            for frame in ImageSequence.Iterator(self.gif)
        ]

        self.label = tk.Label(root, bg="white")
        self.label.pack()

        # Variables animación
        self.frame_index = 0

        # Dirección movimiento
        self.direction_x = 1
        self.direction_y = 1

        # Posición inicial aleatoria
        self.x = random.randint(0, self.root.winfo_screenwidth() - 300)
        self.y = random.randint(0, self.root.winfo_screenheight() - 300)

        self.root.geometry(f"+{self.x}+{self.y}")

        # Eventos
        self.label.bind("<Button-1>", self.toggle_state)

        # Iniciar ciclos
        self.animate()
        self.move()

    # ---------------- ANIMACIÓN ----------------
    def animate(self):
        self.label.config(image=self.frames[self.frame_index])
        self.frame_index = (self.frame_index + 1) % len(self.frames)

        if self.state == "walking":
            delay = 100
        elif self.state == "idle":
            delay = 300  # más lenta
        elif self.state == "listening":
            delay = 50   # más rápida
        else:
            delay = 100

        self.root.after(delay, self.animate)

    # ---------------- MOVIMIENTO ----------------
    def move(self):
        if self.state == "walking":
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()

            sprite_width = self.frames[0].width()
            sprite_height = self.frames[0].height()

            self.x += 5 * self.direction_x
            self.y += 3 * self.direction_y

            if self.x <= 0:
                self.x = 0
                self.direction_x = 1
            elif self.x >= screen_width - sprite_width:
                self.x = screen_width - sprite_width
                self.direction_x = -1

            if self.y <= 0:
                self.y = 0
                self.direction_y = 1
            elif self.y >= screen_height - sprite_height:
                self.y = screen_height - sprite_height
                self.direction_y = -1

            self.root.geometry(f"+{self.x}+{self.y}")

        elif self.state == "listening":
            # Pequeño efecto vibración
            self.root.geometry(f"+{self.x + random.randint(-3,3)}+{self.y + random.randint(-3,3)}")

        self.root.after(40, self.move)

    # ---------------- CAMBIO DE ESTADO ----------------
    def toggle_state(self, event):
        if self.state == "walking":
            self.state = "idle"
        elif self.state == "idle":
            self.state = "listening"
        else:
            self.state = "walking"


if __name__ == "__main__":
    root = tk.Tk()
    pet = DesktopPet(root)
    root.mainloop()