#!/usr/bin/env python3
"""
KTOx Payload – Wifite WiFi Auditor (LCD)
=========================================
Simple, robust wrapper for wifite with LCD display on KTOx_Pi.

Controls:
  UP / DOWN         – Navigate options
  OK / CENTER       – Select / Execute
  KEY3              – Exit payload
"""

import sys
import os
import time
import signal
import subprocess
import threading

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# Hardware detection
try:
    import RPi.GPIO as GPIO
    import LCD_1in44
    from PIL import Image, ImageDraw, ImageFont
    HAS_LCD = True
except (ImportError, RuntimeError):
    HAS_LCD = False

# ─────────────────────────────────────────────────────────────────────────────

PINS = {"UP": 6, "DOWN": 19, "LEFT": 5, "RIGHT": 26, "OK": 13, "KEY1": 21, "KEY2": 20, "KEY3": 16}
LCD = None
WIDTH, HEIGHT = 128, 128
FONT = None

if HAS_LCD:
    GPIO.setmode(GPIO.BCM)
    for pin in PINS.values():
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    LCD = LCD_1in44.LCD()
    LCD.LCD_Init(LCD_1in44.SCAN_DIR_DFT)
    FONT = ImageFont.load_default()

# ─────────────────────────────────────────────────────────────────────────────

running = True
wifite_process = None
output_lines = []
output_lock = threading.Lock()

def cleanup(*_):
    global running, wifite_process
    running = False
    if wifite_process and wifite_process.poll() is None:
        try:
            wifite_process.terminate()
            wifite_process.wait(timeout=2)
        except:
            try:
                wifite_process.kill()
            except:
                pass
    if HAS_LCD:
        try:
            LCD.LCD_Clear()
            GPIO.cleanup()
        except:
            pass
    sys.exit(0)

signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)

def draw_ui(title="", lines=None):
    """Draw UI on LCD."""
    if not HAS_LCD or not LCD:
        return
    try:
        img = Image.new("RGB", (WIDTH, HEIGHT), (10, 0, 0))
        draw = ImageDraw.Draw(img)

        # Title bar
        draw.rectangle((0, 0, WIDTH, 12), fill=(139, 0, 0))
        draw.text((4, 1), title[:20], font=FONT, fill=(192, 57, 43))

        # Content
        y = 16
        if lines:
            for line in lines[-7:]:
                text = str(line)[:20].strip()
                draw.text((2, y), text, font=FONT, fill=(242, 243, 244))
                y += 12

        # Footer
        draw.rectangle((0, 117, WIDTH, 127), fill=(34, 0, 0))
        draw.text((4, 120), "KEY3=Exit", font=FONT, fill=(113, 125, 126))

        LCD.LCD_ShowImage(img, 0, 0)
    except Exception as e:
        pass

def read_wifite_output():
    """Read and display wifite output."""
    global wifite_process, output_lines
    try:
        while wifite_process and wifite_process.poll() is None and running:
            try:
                line = wifite_process.stdout.readline()
                if line:
                    clean_line = line.strip()
                    if clean_line:
                        with output_lock:
                            output_lines.append(clean_line)
                            if len(output_lines) > 50:
                                output_lines = output_lines[-50:]
            except:
                pass
            time.sleep(0.05)
    except:
        pass

def run_wifite_scan():
    """Start wifite scanning."""
    global wifite_process, output_lines
    try:
        output_lines = []
        draw_ui("WIFITE", ["Starting scan...", "Please wait..."])

        wifite_process = subprocess.Popen(
            ["sudo", "wifite", "-i", "wlan1"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        reader_thread = threading.Thread(target=read_wifite_output, daemon=True)
        reader_thread.start()

        return True
    except FileNotFoundError:
        draw_ui("ERROR", ["Wifite not", "installed"])
        time.sleep(2)
        return False
    except Exception as e:
        draw_ui("ERROR", [str(e)[:20]])
        time.sleep(2)
        return False

def show_menu():
    """Show main menu."""
    menu = ["Start Scan", "View Handshakes", "Exit"]
    selected = 0

    while running:
        try:
            img = Image.new("RGB", (WIDTH, HEIGHT), (10, 0, 0))
            draw = ImageDraw.Draw(img)

            # Title
            draw.rectangle((0, 0, WIDTH, 12), fill=(139, 0, 0))
            draw.text((4, 1), "WIFITE", font=FONT, fill=(192, 57, 43))

            # Menu items
            y = 20
            for i, item in enumerate(menu):
                color = (212, 172, 13) if i == selected else (242, 243, 244)
                marker = ">" if i == selected else " "
                draw.text((2, y), f"{marker} {item}", font=FONT, fill=color)
                y += 15

            if HAS_LCD:
                LCD.LCD_ShowImage(img, 0, 0)

            # Button handling
            if HAS_LCD:
                if GPIO.input(PINS["UP"]) == 0:
                    selected = (selected - 1) % len(menu)
                    time.sleep(0.2)
                elif GPIO.input(PINS["DOWN"]) == 0:
                    selected = (selected + 1) % len(menu)
                    time.sleep(0.2)
                elif GPIO.input(PINS["OK"]) == 0:
                    time.sleep(0.2)
                    if selected == 0:
                        show_scan()
                    elif selected == 1:
                        show_handshakes()
                    elif selected == 2:
                        cleanup()
                elif GPIO.input(PINS["KEY3"]) == 0:
                    cleanup()
            else:
                time.sleep(0.1)
        except KeyboardInterrupt:
            cleanup()
        except Exception:
            time.sleep(0.1)

def show_scan():
    """Show scan results."""
    global wifite_process, output_lines

    if not run_wifite_scan():
        return

    while running:
        try:
            with output_lock:
                lines_copy = output_lines.copy()
            draw_ui("WIFITE SCAN", lines_copy)

            if HAS_LCD:
                if GPIO.input(PINS["KEY3"]) == 0:
                    if wifite_process and wifite_process.poll() is None:
                        wifite_process.terminate()
                        try:
                            wifite_process.wait(timeout=1)
                        except:
                            wifite_process.kill()
                    break

            time.sleep(0.1)
        except KeyboardInterrupt:
            if wifite_process:
                wifite_process.terminate()
            break
        except Exception:
            time.sleep(0.1)

def show_handshakes():
    """Show saved handshakes."""
    lines = ["Checking for", "saved handshakes...", ""]

    try:
        result = subprocess.run(
            ["find", "/root/KTOx/loot", "-name", "*.cap", "-o", "-name", "*.pcap"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.stdout:
            handshakes = result.stdout.strip().split('\n')
            lines.extend([os.path.basename(h) for h in handshakes[:5]])
        else:
            lines.append("No handshakes found")
    except:
        lines.append("Error reading files")

    draw_ui("HANDSHAKES", lines)
    time.sleep(3)

def main():
    """Main entry point."""
    global running

    try:
        show_menu()
    except KeyboardInterrupt:
        cleanup()
    except Exception as e:
        if HAS_LCD:
            draw_ui("ERROR", [str(e)[:20]])
            time.sleep(2)
        cleanup()

if __name__ == "__main__":
    main()
