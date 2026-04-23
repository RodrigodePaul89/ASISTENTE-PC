class PetIdentityManager:
    def __init__(self, owner):
        self.owner = owner

    def build_pet_identity_system_prompt(self):
        user_name = self.owner.user_name_memory.strip() or "usuario"
        memory_lines = self.owner.pet_memory_notes[-6:]
        memory_block = "\n".join(f"- {item}" for item in memory_lines) if memory_lines else "- (sin notas aun)"
        return (
            f"Tu nombre es {self.owner.pet_name}. "
            "Eres la mascota asistente de escritorio de esta app. "
            "Habla siempre en primera persona (yo/me/mi), nunca como si fueras una tercera persona. "
            "Si te hablan directamente, asume que te hablan a ti, la mascota. "
            "Actua como una mascota amigable y servicial. "
            "Ten pensamiento propio, pero no seas creativa al inventar acciones del sistema que no puedas ejecutar. "
            f"El usuario principal se llama {user_name}. "
            "Mantente breve, clara y util; no inventes acciones del sistema que no puedas ejecutar. "
            "Memoria actual de la mascota:\n"
            f"{memory_block}"
        )

    def format_pet_memory(self):
        lines = [f"Nombre de la mascota: {self.owner.pet_name}"]
        if self.owner.user_name_memory:
            lines.append(f"Nombre del usuario: {self.owner.user_name_memory}")
        else:
            lines.append("Nombre del usuario: (sin definir)")

        if self.owner.pet_memory_notes:
            lines.append("Recuerdos:")
            for note in self.owner.pet_memory_notes[-8:]:
                lines.append(f"- {note}")
        else:
            lines.append("Recuerdos: (vacio)")

        return "\n".join(lines)
