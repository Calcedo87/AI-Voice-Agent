def execute(action):
    actions = {
        "light_on": lambda: print("💡 Luz encendida"),
        "light_off": lambda: print("💤 Luz apagada"),
        "door_open": lambda: print("🚪 Puerta abierta"),
        "door_close": lambda: print("🔒 Puerta cerrada")
    }
    if action in actions:
        actions[action]()
    else:
        print(f"[!] Acción desconocida: {action}")

