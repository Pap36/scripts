import time
import pyautogui
import keyboard

HOLDING_KEYS = ['cmd', 'ctrl', 'alt', 'shift']

def reproduce_actions(file_path, customFirstInput=None, secondFirstInput=None):

    specialKeys = []

    with open(file_path, 'r') as file:
        prevTime = None
        for line in file:
            action = line.strip().split()
            time = float(action[-1])
            print(action)
            if action[0] == 'Move':
                x, y = map(int, action[1:3])
                pyautogui.moveTo(x=x, y=y, duration=time-prevTime if prevTime is not None else 0)
            elif action[0] == 'Clicked':
                x, y = map(int, action[1:3])
                button = action[3].split('.')[1]
                pyautogui.click(x=x, y=y, button=button)
            elif action[0] == 'Scroll':
                x, y = map(int, action[1:3])
                _, dy = map(int, action[3:5])
                pyautogui.scroll(dy, x, y)
            elif action[0] == 'Press':
                key = action[1]
                if key == '*':
                    key = customFirstInput
                elif key == '?':
                    key = secondFirstInput

                if key in HOLDING_KEYS:
                    keyboard.press(key)
                else:
                    try:
                        keyboard.send(key)
                    except:
                        keyboard.write(key)
            elif action[0] == 'Release':
                key = action[1]
                if key in HOLDING_KEYS:
                    keyboard.release(key)
            
            prevTime = time


for count in range(500):
    firstInput = str(count)[:2]
    secondInput = str(count)[2:]
    reproduce_actions('recorded_actions.txt', firstInput, secondInput)
    time.sleep(1)


