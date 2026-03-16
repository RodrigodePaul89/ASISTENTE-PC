import random
from pathlib import Path


class PetDesignManager:
    def __init__(self, owner):
        self.owner = owner

    def discover_available_styles(self):
        img_root = self.owner.asset_dir.parent / "img"
        required = ["Idle.png", "Walk.png"]

        discovered = []
        if img_root.exists():
            for entry in img_root.iterdir():
                if not entry.is_dir():
                    continue
                if all((entry / req).exists() for req in required):
                    discovered.append(entry.name)

        if discovered:
            preferred = ["Musketeer", "Knight", "Enchantress"]
            preferred_found = [name for name in preferred if name in discovered]

            if preferred_found:
                print(f"[Mascota] Estilos detectados: {', '.join(preferred_found)}")
                return preferred_found

            discovered_sorted = sorted(discovered)
            print(f"[Mascota] Estilos detectados: {', '.join(discovered_sorted)}")
            return discovered_sorted

        return ["Musketeer", "Knight", "Enchantress"]

    def build_animation_sources_for_style(self, style_name):
        style_base = (Path("..") / "img" / style_name).as_posix()

        return {
            "walking": [
                f"{style_base}/Walk.png",
                f"{style_base}/walk.png",
                f"{style_base}/Run.png",
                "walk.gif",
                "walking.gif",
                "ranaa.gif",
                "rana.gif",
                "ranaaa.gif",
            ],
            "idle": [
                f"{style_base}/Idle.png",
                "idle.gif",
                "breathing.gif",
                "ranaaa.gif",
                "ranaa.gif",
            ],
            "running": [
                f"{style_base}/Run.png",
                f"{style_base}/Walk.png",
                f"{style_base}/walk.png",
            ],
            "jump": [
                f"{style_base}/Jump.png",
                f"{style_base}/Run.png",
                f"{style_base}/Walk.png",
            ],
            "dead": [
                f"{style_base}/Dead.png",
                f"{style_base}/Hurt.png",
                f"{style_base}/Idle.png",
            ],
            "listening": [
                f"{style_base}/Attack_4.png",
                f"{style_base}/Attack_3.png",
                f"{style_base}/Attack_2.png",
                f"{style_base}/Attack_1.png",
                f"{style_base}/Jump.png",
                f"{style_base}/Hurt.png",
                "listening.gif",
                f"{style_base}/Idle.png",
            ],
            "attack_1": [f"{style_base}/Attack_1.png", f"{style_base}/Attack_2.png"],
            "attack_2": [f"{style_base}/Attack_2.png", f"{style_base}/Attack_3.png"],
            "attack_3": [f"{style_base}/Attack_3.png", f"{style_base}/Attack_4.png"],
            "attack_4": [f"{style_base}/Attack_4.png", f"{style_base}/Attack_1.png"],
        }

    def choose_next_style(self):
        if len(self.owner.available_styles) <= 1:
            return self.owner.current_style

        if not self.owner.style_cycle_queue:
            self.owner.style_cycle_queue = [
                style for style in self.owner.available_styles if style != self.owner.current_style
            ]
            random.shuffle(self.owner.style_cycle_queue)

        return self.owner.style_cycle_queue.pop(0)
