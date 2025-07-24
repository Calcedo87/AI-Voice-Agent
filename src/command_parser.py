def handle_command(text):
    commands = {
        "enciende la luz": "light_on",
        "apaga la luz": "light_off",
        "abre la puerta": "door_open",
        "cierra la puerta": "door_close"
    }
    return commands.get(text.lower().strip())

