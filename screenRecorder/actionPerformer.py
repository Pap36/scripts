import sys
import time
import pyautogui
import keyboard
import pynput

HOLDING_KEYS = ['cmd', 'ctrl', 'alt', 'shift']

def reproduce_actions(file_path, customFirstInput=None, secondFirstInput=None):

    with open(file_path, 'r') as file:
        prevTime = None
        lastLocation = None
        for line in file:
            action = line.strip().split()
            time = float(action[-1])
            print(action)
            if action[0] == 'Move':
                x, y = map(int, action[1:3])
                if lastLocation != (x, y):
                    pyautogui.moveTo(x=x, y=y, duration=time-prevTime if prevTime is not None else 0)
                    lastLocation = (x, y)
            elif action[0] == 'Clicked':
                x, y = map(int, action[1:3])
                button = action[3].split('.')[1]
                click_count = int(action[4])
                if click_count > 1:
                    if button == 'left':
                        mouseButton = pynput.mouse.Button.left
                    elif button == 'right':
                        mouseButton = pynput.mouse.Button.right
                    pynput.mouse.Controller().click(button=mouseButton, count=2)
                else :
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
            elif action[0] == 'Copy':
                # If on Mac, use 'cmd+c' to copy
                # If on Windows, use 'ctrl+c' to copy
                if 'darwin' in sys.platform:
                    pyautogui.hotkey('command c')
                else:
                    pyautogui.hotkey('ctrl c')
            elif action[0] == 'Paste':
                # If on Mac, use 'cmd+v' to paste
                # If on Windows, use 'ctrl+v' to paste
                if 'darwin' in sys.platform:
                    pyautogui.hotkey('command v')
                else:
                    pyautogui.hotkey('ctrl v')
            
            prevTime = time


for count in range(1):
    firstInput = str(count)[:2]
    secondInput = str(count)[2:]
    reproduce_actions('recorded_actions.txt', firstInput, secondInput)
    time.sleep(1)


