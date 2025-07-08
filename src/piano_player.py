import time
import keyboard
import json
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# --- Your existing key processing logic (mostly unchanged) ---
key_state = {}
key_lock = threading.Lock()

def preprocess_data(data):
    """
    Processes the raw note data into a dictionary keyed by timestamp.
    Also returns the maximum timestamp found in the data.
    """
    timestamp_dict = {}
    max_timestamp = 0
    for note in data:
        try:
            note_time = int(note["time"])
        except (ValueError, TypeError):
            # print(f"Warning: Skipping note with invalid time format: {note}") # Log to GUI later
            continue

        key = note["key"]
        if note_time in timestamp_dict:
            timestamp_dict[note_time].append(key)
        else:
            timestamp_dict[note_time] = [key]
        if note_time > max_timestamp:
            max_timestamp = note_time
    return timestamp_dict, max_timestamp

def press_and_release_key(pressed_key, duration):
    """
    Handles pressing and releasing a single key, managing potential overlaps.
    Uses a lock to prevent race conditions when accessing key_state.
    """
    global key_state
    try:
        with key_lock:
            if key_state.get(pressed_key, False):
                keyboard.release(pressed_key)
                time.sleep(0.005) # Short pause before re-press

            keyboard.press(pressed_key)
            key_state[pressed_key] = True

        time.sleep(duration) # Hold the key

    finally:
        with key_lock:
            keyboard.release(pressed_key)
            key_state[pressed_key] = False

def map_and_press_key(key_str, duration, key_mapping):
    """
    Maps the key string (e.g., '1Key0') to a keyboard character
    and starts a thread to press/release it.
    """
    parts = key_str.split("Key")
    if len(parts) != 2:
        # print(f"Warning: Unexpected key format: '{key_str}'") # Log to GUI
        return

    key_index_str_raw = parts[1]
    key_index_str_extracted = key_index_str_raw.strip()

    if not key_index_str_extracted:
        # print(f"Warning: Extracted empty string for key: '{key_str}'. Skipping.") # Log
        return

    try:
        key_index = int(key_index_str_extracted)
        pressed_key_char = key_mapping.get(key_index)

        if pressed_key_char:
            threading.Thread(target=press_and_release_key, args=(pressed_key_char, duration), daemon=True).start()
        # else:
            # print(f"Warning: No mapping for key index: {key_index}") # Log
    except ValueError:
        # print(f"ValueError: Could not parse: '{key_index_str_extracted}' from '{key_str}'") # Log
        pass
    except Exception as e:
        # print(f"Error processing key string '{key_str}': {e}") # Log
        pass

# --- Default Configuration (can be overridden by GUI) ---
DEFAULT_KEY_MAPPING = {
    0: 'y', 1: 'u', 2: 'i', 3: 'o', 4: 'p',
    5: 'h', 6: 'j', 7: 'k', 8: 'l', 9: ';',
    10: 'n', 11: 'm', 12: ',', 13: '.', 14: '/',
}

# --- GUI Application Class ---
class PianoPlayerApp:
    def __init__(self, master):
        self.master = master
        master.title("Auto Piano Player")
        master.geometry("550x220") # Adjusted size

        # Add this line to make the window always on top
        master.attributes('-topmost', True)

        self.song_data = None
        self.timestamp_dict = {}
        self.max_timestamp = 0
        self.current_song_time_ms = 0 # In milliseconds, song's internal time
        self.playback_start_real_time = 0 # time.perf_counter()

        self.is_playing = False
        self.is_paused = False
        self.playback_thread = None
        self.stop_event = threading.Event() # Used to signal the playback thread to stop
        self.pause_event = threading.Event() # Used to signal pause (set) and resume (clear)
        self.pause_event.set() # Start in a "not paused" state (event is set = proceed)

        self.seek_target_ms = -1 # Target time for seeking, -1 means no seek request

        # --- Style ---
        style = ttk.Style()
        style.theme_use('clam') # Or 'alt', 'default', 'classic'

        # --- Variables ---
        self.filename_var = tk.StringVar(value="No file selected")
        self.speed_multiplier_var = tk.StringVar(value="1.0")
        self.hold_duration_var = tk.StringVar(value="0.25") # Base duration
        self.status_var = tk.StringVar(value="Load a song to begin.")
        self.time_display_var = tk.StringVar(value="00:00 / 00:00")

        # --- UI Elements ---
        # File Selection
        file_frame = ttk.LabelFrame(master, text="Song File")
        file_frame.pack(padx=10, pady=5, fill="x")
        ttk.Button(file_frame, text="Browse...", command=self.browse_file).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Label(file_frame, textvariable=self.filename_var, wraplength=380).pack(side=tk.LEFT, padx=5, pady=5, expand=True, fill="x")

        # Parameters
        params_frame = ttk.Frame(master)
        params_frame.pack(padx=10, pady=5, fill="x")

        ttk.Label(params_frame, text="Speed:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(params_frame, textvariable=self.speed_multiplier_var, width=5).grid(row=0, column=1, padx=5, pady=5, sticky="w")
        ttk.Label(params_frame, text="x").grid(row=0, column=2, padx=0, pady=5, sticky="w")

        ttk.Label(params_frame, text="Hold (s):").grid(row=0, column=3, padx=15, pady=5, sticky="w")
        ttk.Entry(params_frame, textvariable=self.hold_duration_var, width=5).grid(row=0, column=4, padx=5, pady=5, sticky="w")

        # Controls
        controls_frame = ttk.Frame(master)
        controls_frame.pack(padx=10, pady=10)
        self.play_button = ttk.Button(controls_frame, text="Play", command=self.play_song, width=10)
        self.play_button.pack(side=tk.LEFT, padx=5)
        self.pause_button = ttk.Button(controls_frame, text="Pause", command=self.pause_resume_song, state=tk.DISABLED, width=10)
        self.pause_button.pack(side=tk.LEFT, padx=5)
        self.stop_button = ttk.Button(controls_frame, text="Stop", command=self.stop_song, state=tk.DISABLED, width=10)
        self.stop_button.pack(side=tk.LEFT, padx=5)

        # Seek/Progress Bar
        progress_frame = ttk.Frame(master)
        progress_frame.pack(padx=10, pady=5, fill="x")
        self.seek_scale = ttk.Scale(progress_frame, from_=0, to=100, orient=tk.HORIZONTAL, command=self.seek_song_slider_dragged, length=400)
        self.seek_scale.pack(side=tk.LEFT, padx=5, expand=True, fill="x")
        self.seek_scale.bind("<ButtonRelease-1>", self.seek_song_slider_released) # For actual seek on release
        self.seek_scale.config(state=tk.DISABLED)
        ttk.Label(progress_frame, textvariable=self.time_display_var, width=12).pack(side=tk.LEFT, padx=5)

        # Status Bar
        status_bar = ttk.Label(master, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill="x")

        self.master.protocol("WM_DELETE_WINDOW", self.on_closing) # Handle window close

        # Initialize key mapping (could be loaded from config later)
        self.key_mapping = DEFAULT_KEY_MAPPING
        self.update_gui_state() # Initial state

    def browse_file(self):
        filepath = filedialog.askopenfilename(
            title="Select Song File",
            filetypes=(("Text files", "*.txt"), ("JSON files", "*.json"), ("All files", "*.*"))
        )
        if filepath:
            self.filename_var.set(filepath)
            self.status_var.set(f"Selected: {filepath.split('/')[-1]}")
            self.load_song_data()
            self.update_gui_state()

    def load_song_data(self):
        filepath = self.filename_var.get()
        if not filepath or filepath == "No file selected":
            self.status_var.set("Error: No file selected to load.")
            return False
        try:
            with open(filepath, "r", encoding="utf-16") as file:
                raw_data = json.load(file)

            # —— NEW FORMAT DETECTION ——
            # Case A: single dict with "songNotes" at the top
            if isinstance(raw_data, dict) and "songNotes" in raw_data:
                notes = raw_data["songNotes"]

            # Case B: list of song‑dicts (take the first one)
            elif isinstance(raw_data, list) and raw_data and isinstance(raw_data[0], dict) and "songNotes" in raw_data[0]:
                notes = raw_data[0]["songNotes"]

            # Case C: plain list of {key,time} entries
            elif isinstance(raw_data, list) and all(isinstance(item, dict) and "key" in item and "time" in item for item in raw_data[:min(5, len(raw_data))]):
                notes = raw_data

            else:
                messagebox.showerror("Load Error", "Unrecognized song file format.")
                self.status_var.set("Error: unknown format.")
                return False

            self.song_data = notes
            self.timestamp_dict, self.max_timestamp = preprocess_data(self.song_data)
            if not self.timestamp_dict:
                self.status_var.set("No valid notes found in the file.")
                messagebox.showinfo("Info", "No valid notes found in the file.")
                self.song_data = None
                return False

            self.seek_scale.config(to=self.max_timestamp, state=tk.NORMAL if self.max_timestamp > 0 else tk.DISABLED)
            self.current_song_time_ms = 0
            self.seek_scale.set(0)
            self.update_time_display()
            self.status_var.set(f"Loaded: {filepath.split('/')[-1]}. Max time: {self.max_timestamp / 1000:.2f}s")
            return True
        except FileNotFoundError:
            self.status_var.set(f"Error: File not found: {filepath}")
            messagebox.showerror("Load Error", f"File not found: {filepath}")
            self.song_data = None
        except (json.JSONDecodeError, KeyError) as e:
            self.status_var.set(f"Error parsing JSON: {e}")
            messagebox.showerror("Load Error", f"Error parsing JSON file: {e}\nEnsure it's valid JSON.")
            self.song_data = None
        except Exception as e:
            self.status_var.set(f"Unexpected error loading file: {e}")
            messagebox.showerror("Load Error", f"An unexpected error occurred: {e}")
            self.song_data = None
        return False


    def get_playback_params(self):
        try:
            speed = float(self.speed_multiplier_var.get())
            if speed <= 0:
                messagebox.showerror("Error", "Speed multiplier must be positive.")
                return None, None
        except ValueError:
            messagebox.showerror("Error", "Invalid speed multiplier. Please enter a number.")
            return None, None

        try:
            hold = float(self.hold_duration_var.get())
            if hold <= 0:
                messagebox.showerror("Error", "Hold duration must be positive.")
                return None, None
        except ValueError:
            messagebox.showerror("Error", "Invalid hold duration. Please enter a number.")
            return None, None
        return speed, hold

    def play_song(self):
        if self.is_playing and not self.is_paused: # Already playing
            return
        if not self.song_data:
            if not self.load_song_data(): # Try to load if not already
                return

        speed, hold = self.get_playback_params()
        if speed is None: return

        if self.playback_thread and self.playback_thread.is_alive():
             # If paused, resume it. If stopped and re-playing, should be fine.
            if self.is_paused:
                self.is_paused = False
                self.pause_event.set() # Signal playback loop to continue
                self.status_var.set("Resuming...")
                self.update_gui_state()
                return # Already have a thread, just unpause it.

        # If no active thread, or starting fresh
        self.is_playing = True
        self.is_paused = False
        self.stop_event.clear() # Ensure stop flag is cleared
        self.pause_event.set()  # Ensure pause flag allows running

        # If current_song_time_ms is at the end, reset to start for re-play
        if self.current_song_time_ms >= self.max_timestamp:
            self.current_song_time_ms = 0
            self.seek_scale.set(0)

        self.status_var.set(f"Playing... (Speed: {speed}x, Hold: {hold}s)")
        self.playback_start_real_time = time.perf_counter() - (self.current_song_time_ms / 1000.0) / speed

        self.playback_thread = threading.Thread(target=self._playback_loop, args=(speed, hold), daemon=True)
        self.playback_thread.start()
        self.update_gui_state()
        self.master.after(100, self.update_progress) # Start periodic progress updates

    def _playback_loop(self, speed_multiplier, base_note_duration):
        """The actual playback logic running in a separate thread."""
        # adjusted_duration = base_note_duration / speed_multiplier # if you want notes shorter at high speed
        adjusted_duration = base_note_duration # Keep note duration constant

        # local_time_counter is the song's internal time in ms, starts from current_song_time_ms
        local_time_counter = self.current_song_time_ms

        try:
            while local_time_counter <= self.max_timestamp + (adjusted_duration * 1000): # Buffer for last note
                if self.stop_event.is_set():
                    break # Exit if stop is signalled

                self.pause_event.wait() # This will block if pause_event is cleared (paused)

                # --- Seeking Logic ---
                if self.seek_target_ms != -1:
                    local_time_counter = self.seek_target_ms
                    self.current_song_time_ms = local_time_counter # Update shared variable
                    # Adjust playback_start_real_time to reflect the jump
                    self.playback_start_real_time = time.perf_counter() - (local_time_counter / 1000.0) / speed_multiplier
                    self.seek_target_ms = -1 # Reset seek request
                    # print(f"Seeked to {local_time_counter}ms")


                # Play notes for the current millisecond
                if local_time_counter in self.timestamp_dict:
                    for key_str in self.timestamp_dict[local_time_counter]:
                        map_and_press_key(key_str, adjusted_duration, self.key_mapping)

                self.current_song_time_ms = local_time_counter # Update for GUI progress

                # Increment the song time counter
                local_time_counter += 1

                # Calculate the target elapsed real time based on the speed multiplier
                target_elapsed_real_time = (local_time_counter / 1000.0) / speed_multiplier
                # Calculate how much real time has actually passed since (adjusted) start
                current_elapsed_real_time = time.perf_counter() - self.playback_start_real_time
                wait_time = target_elapsed_real_time - current_elapsed_real_time

                if wait_time > 0:
                    # Check stop_event frequently during sleep using smaller sleep intervals
                    sleep_interval = 0.001 # Check every 1ms
                    num_intervals = int(wait_time / sleep_interval)
                    for _ in range(num_intervals):
                        if self.stop_event.is_set() or not self.pause_event.is_set(): break
                        time.sleep(sleep_interval)
                    if self.stop_event.is_set() or not self.pause_event.is_set(): break # Check after loop
                    remaining_wait = wait_time - (num_intervals * sleep_interval)
                    if remaining_wait > 0: time.sleep(remaining_wait)


                # Safety break (already in your original code, good to keep)
                expected_total_runtime = (self.max_timestamp / 1000.0) / speed_multiplier
                if current_elapsed_real_time > expected_total_runtime + 10 and self.max_timestamp > 0 : # Add 10s buffer
                    self.status_var.set("Playback exceeded expected runtime. Stopping.")
                    break
            if not self.stop_event.is_set(): # If loop finished normally
                self.master.after(0, self.playback_finished)

        except Exception as e:
            print(f"Error in playback loop: {e}") # Should show this in GUI status
            self.master.after(0, lambda: self.status_var.set(f"Playback error: {e}"))
        finally:
            self.master.after(0, self.cleanup_after_playback)


    def cleanup_after_playback(self):
        """Called when playback loop ends (normally, by stop, or error)."""
        self.is_playing = False
        self.is_paused = False # Ensure pause state is reset
        self.pause_event.set() # Ensure it's not blocking for next play
        # Don't reset stop_event here, it's managed by play/stop
        self.update_gui_state()
        # self.status_var.set("Playback stopped." if self.stop_event.is_set() else "Playback finished.") # Handled by caller
        self.release_all_keys_gui()


    def playback_finished(self):
        """Called when playback completes naturally."""
        self.status_var.set("Playback finished.")
        self.current_song_time_ms = self.max_timestamp # Ensure slider goes to end
        self.update_progress() # Final update for slider and time display
        # cleanup_after_playback will be called by the thread's finally block.

    def pause_resume_song(self):
        if not self.is_playing:
            return

        if self.is_paused: # Currently paused, so resume
            self.is_paused = False
            self.pause_event.set() # Signal playback loop to continue
            # Recalculate start time to account for pause duration
            # current song time hasn't changed, but real time has passed
            speed, _ = self.get_playback_params() # get current speed
            if speed is None: speed = 1.0 # fallback
            self.playback_start_real_time = time.perf_counter() - (self.current_song_time_ms / 1000.0) / speed
            self.status_var.set("Resuming...")
            self.master.after(100, self.update_progress())
        else: # Currently playing, so pause
            self.is_paused = True
            self.pause_event.clear() # Signal playback loop to pause (wait)
            self.status_var.set("Paused.")
        self.update_gui_state()

    def stop_song(self):
        if self.playback_thread and self.playback_thread.is_alive():
            self.status_var.set("Stopping...")
            self.stop_event.set()  # Signal thread to stop
            self.pause_event.set() # Unblock if paused, so it can see the stop_event
            # The thread's finally block will call cleanup_after_playback
            # Wait a very short time for thread to notice stop, then force GUI update
            self.master.after(100, self._check_thread_stopped)
        else: # If no thread, just reset state
            self.current_song_time_ms = 0
            self.cleanup_after_playback() # This resets GUI and flags
            self.status_var.set("Playback stopped.")


    def _check_thread_stopped(self):
        if self.playback_thread and self.playback_thread.is_alive():
            # If still alive after a bit, it might be stuck in a long sleep
            # This is a fallback; ideally, the loop checks stop_event frequently
            self.master.after(200, self._check_thread_stopped) # Check again
        else:
            # Thread has now exited, ensure everything is clean
            self.cleanup_after_playback()
            self.status_var.set("Playback stopped.")
            if self.current_song_time_ms >= self.max_timestamp: # If stopped at the end
                self.current_song_time_ms = 0 # Reset for next play
            self.update_progress() # Update slider to current_song_time_ms (could be 0)


    def seek_song_slider_dragged(self, value_str):
        # This is called continuously while dragging.
        # We only update the time display, actual seek happens on release.
        if self.song_data and self.max_timestamp > 0:
            seek_val_ms = int(float(value_str))
            self.current_song_time_ms = seek_val_ms # Tentatively update for display
            self.update_time_display()

    def seek_song_slider_released(self, event):
        # This is called when the user releases the mouse button on the slider.
        if self.song_data and self.max_timestamp > 0:
            seek_val_ms = int(self.seek_scale.get())
            self.seek_target_ms = seek_val_ms
            self.current_song_time_ms = seek_val_ms # Ensure this is also updated for immediate feedback

            if self.is_playing and not self.is_paused:
                # If playing, the playback loop will pick up seek_target_ms
                # We might need to adjust playback_start_real_time if it was actively playing
                speed, _ = self.get_playback_params()
                if speed is None: speed = 1.0
                self.playback_start_real_time = time.perf_counter() - (self.current_song_time_ms / 1000.0) / speed
                self.status_var.set(f"Seeking to {self.current_song_time_ms / 1000:.2f}s...")
            elif self.is_playing and self.is_paused:
                 # If paused, update current time. When resumed, it will start from here.
                self.status_var.set(f"Seek to {self.current_song_time_ms / 1000:.2f}s (while paused).")
            else: # Not playing
                self.status_var.set(f"Seek to {self.current_song_time_ms / 1000:.2f}s (stopped).")
            self.update_time_display() # Update display based on seek

    def update_progress(self):
        """Periodically called to update the GUI progress bar and time."""
        if self.is_playing and not self.is_paused and self.max_timestamp > 0:
            self.seek_scale.set(self.current_song_time_ms)
            self.update_time_display()
            self.master.after(100, self.update_progress) # Schedule next update
        elif self.max_timestamp > 0: # Update display even if paused/stopped
             self.seek_scale.set(self.current_song_time_ms)
             self.update_time_display()


    def format_time(self, ms):
        if ms < 0: ms = 0
        seconds = int((ms / 1000) % 60)
        minutes = int((ms / (1000 * 60)) % 60)
        return f"{minutes:02d}:{seconds:02d}"

    def update_time_display(self):
        current_t_str = self.format_time(self.current_song_time_ms)
        total_t_str = self.format_time(self.max_timestamp)
        self.time_display_var.set(f"{current_t_str} / {total_t_str}")

    def update_gui_state(self):
        """Enable/disable buttons based on playback state."""
        if not self.song_data:
            self.play_button.config(state=tk.DISABLED)
            self.pause_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.DISABLED)
            self.seek_scale.config(state=tk.DISABLED)
        else:
            self.seek_scale.config(state=tk.NORMAL)
            if self.is_playing:
                self.play_button.config(state=tk.DISABLED)
                self.pause_button.config(state=tk.NORMAL, text="Resume" if self.is_paused else "Pause")
                self.stop_button.config(state=tk.NORMAL)
            else: # Stopped or never started
                self.play_button.config(state=tk.NORMAL)
                self.pause_button.config(state=tk.DISABLED, text="Pause")
                self.stop_button.config(state=tk.DISABLED)

    def release_all_keys_gui(self):
        """Releases any potentially stuck keys (called from GUI thread)."""
        # print("GUI: Releasing any potentially stuck keys...")
        with key_lock:
            for key_char in self.key_mapping.values():
                if key_state.get(key_char, False):
                    try:
                        keyboard.release(key_char)
                    except Exception: # keyboard lib might complain if context changes
                        pass
                    key_state[key_char] = False
        # print("GUI: Cleanup complete.")

    def on_closing(self):
        if self.is_playing:
            if messagebox.askokcancel("Quit", "Song is playing. Stop playback and quit?"):
                self.stop_song() # Attempt graceful stop
                # Wait a moment for thread to hopefully stop
                # This is a bit of a hack; proper thread join with timeout is better
                # but can hang GUI if thread is unresponsive.
                self.master.after(250, self._perform_close)
            else:
                return # Don't close
        else:
            self._perform_close()

    def _perform_close(self):
        # Ensure thread is really signalled to stop, even if stop_song had issues
        self.stop_event.set()
        self.pause_event.set() # Unblock any waits
        if self.playback_thread and self.playback_thread.is_alive():
            # print("Waiting for playback thread to join...")
            self.playback_thread.join(timeout=0.5) # Brief wait
        self.release_all_keys_gui()
        self.master.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = PianoPlayerApp(root)
    try:
        # This is needed for keyboard library to work correctly sometimes,
        # especially if it needs admin rights for low-level hooks.
        # Running the script as admin might be necessary on Windows.
        if keyboard.is_modifier("shift"): # dummy check to initialize
            pass
    except Exception as e:
        print(f"Note: Keyboard library check: {e}")
        if "requires Sudo" in str(e) or "admin" in str(e).lower():
            messagebox.showwarning("Permissions",
                                   "Keyboard control might require administrator privileges (e.g., run as Sudo on Linux or 'Run as administrator' on Windows) to function correctly, especially for sending keys to other applications.")

    root.mainloop()
