import time
from pynput.mouse import Listener as MouseListener
from pynput.keyboard import Listener as KeyboardListener

def record_input():
    events = []
    click_count = 0
    last_click_position = None

    def on_click(x, y, button, pressed):
        nonlocal click_count, last_click_position

        if last_click_position == (x, y):
            click_count += 1
        else:
            click_count = 1

        last_click_position = (x, y)

        action = "Clicked" if pressed else "Released"
        events.append(f"Move {int(x)} {int(y)} {time.time()}")
        events.append(f"{action} {int(x)} {int(y)} {button} {time.time()}")
        print(f"{action} at ({x}, {y}) with {button}")

        if click_count >= 3:
            stop_recording()

    def on_scroll(x, y, dx, dy):
        events.append(f"Move {int(x)} {int(y)} {time.time()}")
        events.append(f"Scroll {int(x)} {int(y)} {int(dx)} {int(dy)} {time.time()}")
        print(f"Scrolled {dx} at {x}, {y}")

    def convertKey(key):
        if 'Key' not in str(key):
            return str(key).replace("'", "")
        else:
            return str(key).split('.')[1].replace("'", "")

    def on_press(key):
        events.append('Press ' + convertKey(key) + " " + str(time.time()))
        print(f"Press {key}")

    def on_release(key):
        events.append('Release ' + convertKey(key) + " " + str(time.time()))
        print(f"Release {key}")

    def stop_recording():
        mouse_listener.stop()
        keyboard_listener.stop()

    with MouseListener(on_click=on_click, on_scroll=on_scroll) as mouse_listener:
        with KeyboardListener(on_press=on_press, on_release=on_release) as keyboard_listener:
            mouse_listener.join()
            keyboard_listener.join()

    return events

events = record_input()


# Store recorded actions in a text file
with open("recorded_actions.txt", "w") as file:
    for event in events:
        file.write(str(event) + "\n")
