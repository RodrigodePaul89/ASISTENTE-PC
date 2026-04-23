import queue


class UIEventController:
    def __init__(self, owner):
        self.owner = owner

    def process_ui_queue(self):
        if self.owner.is_destroying:
            return

        while True:
            try:
                action, payload = self.owner.ui_queue.get_nowait()
            except queue.Empty:
                break

            if action == "set_state":
                self.owner.state = payload
            elif action == "chat_response":
                self.owner.chat_request_in_flight = False
                self.owner.append_chat_message("Mascota", payload)
            elif action == "chat_status":
                self.owner.set_chat_status(payload)

        self.owner.root.after(120, self.process_ui_queue)
