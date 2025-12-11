import os
import sys
import tempfile
import threading
from gtts import gTTS
import pygame
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                            QWidget, QPushButton, QLabel, QSlider, QGroupBox,
                            QComboBox, QSpinBox)
from PyQt5.QtCore import Qt, QTimer

class TimelineSlider(QSlider):
    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 10px;
                background: #333333;
                border-radius: 5px;
            }
            QSlider::handle:horizontal {
                background: #007acc;
                width: 18px;
                margin: -4px 0;
                border-radius: 9px;
            }
            QSlider::sub-page:horizontal {
                background: #007acc;
                border-radius: 5px;
            }
        """)

class ExamTimer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Exam Timer with Audio Alerts")
        self.setMinimumSize(800, 700)
        
        # Set dark theme colors (inspired by Visual Studio dark theme)
        self.bg_color = '#1e1e1e'  # Main background
        self.fg_color = '#d4d4d4'  # Text foreground
        self.accent_bg = '#333333'  # Widget background
        self.button_bg = '#007acc'  # Accent blue for buttons
        self.button_fg = '#ffffff'  # Button text
        self.active_bg = '#005f9e'  # Active button
        self.border_color = '#3c3c3c'  # Borders
        self.muted_fg = '#858585'   # Muted text for italics
        
        # Initialize pygame mixer for audio with better settings
        pygame.mixer.pre_init(44100, -16, 2, 2048)  # Better audio quality settings
        pygame.mixer.init()
        pygame.mixer.set_num_channels(8)  # Allow multiple sounds to play simultaneously
        
        # Timer variables
        self.total_seconds = 8 * 60  # Default 8 minutes
        self.remaining_seconds = 0
        self.elapsed_seconds = 0
        self.running = False
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_timer)
        self.alerts_triggered = set()
        self.temp_dir = tempfile.mkdtemp()
        
        # Alert time points (in seconds from start)
        self.alert_times = {
            'enter_room': 90,  # 1.5 minutes
            'sleep': 450,      # 7.5 minutes
            'two_min_remaining': None,  # Calculated dynamically
            'end': None        # Calculated dynamically
        }
        
        # Voice options
        self.voice_options = [
            "en-US-AriaNeural",
            "en-US-GuyNeural",
            "en-US-JennyNeural",
            "en-GB-RyanNeural",
            "en-GB-SoniaNeural"
        ]
        self.current_voice = "en-US-AriaNeural"
        self.fine_resolution = False
        
        self.init_ui()
    
    def init_ui(self):
        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Timeline slider with resolution control
        timeline_container = QWidget()
        timeline_layout = QVBoxLayout(timeline_container)
        
        # Timeline slider
        self.timeline = TimelineSlider(Qt.Horizontal)
        self.timeline.setRange(0, self.total_seconds)
        self.timeline.setValue(0)
        self.timeline.setSingleStep(60)  # Default to coarse (1 minute) steps
        
        # Connect signals
        self.timeline.valueChanged.connect(self.seek_timer)
        
        # Set up mouse hover events for resolution change
        def enter_event(event):
            self.timeline.setSingleStep(10)  # Fine adjustment on hover
            
        def leave_event(event):
            self.timeline.setSingleStep(60)  # Coarse adjustment when not hovering
            
        # Apply the event handlers
        self.timeline.enterEvent = lambda e: enter_event(e)
        self.timeline.leaveEvent = lambda e: leave_event(e)
        
        # Tooltip
        self.timeline.setToolTip("Drag to seek through the exam time\nHover for fine adjustment (10s), move away for coarse (1m)")
        
        # Add to layout
        timeline_layout.addWidget(QLabel("Timeline (drag to seek):"))
        timeline_layout.addWidget(self.timeline)
        layout.addWidget(timeline_container)
        
        # Timer display
        self.timer_label = QLabel("00:00")
        self.timer_label.setAlignment(Qt.AlignCenter)
        self.timer_label.setStyleSheet("""
            QLabel {
                font-size: 72px;
                font-weight: bold;
                color: #d4d4d4;
                margin: 20px 0;
            }
        """)
        layout.addWidget(self.timer_label)
        
        # Elapsed time
        self.elapsed_label = QLabel("Elapsed: 00:00")
        self.elapsed_label.setAlignment(Qt.AlignCenter)
        self.elapsed_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                color: #858585;
                margin-bottom: 20px;
            }
        """)
        layout.addWidget(self.elapsed_label)
        
        # Controls
        controls_layout = QHBoxLayout()
        
        # Duration controls
        duration_group = QGroupBox("Total Exam Duration")
        duration_layout = QHBoxLayout(duration_group)
        
        duration_layout.addWidget(QLabel("Duration:"))
        self.duration_min = QSpinBox()
        self.duration_min.setRange(0, 120)
        self.duration_min.setValue(8)
        self.duration_min.setSuffix(" min")
        self.duration_min.valueChanged.connect(self.update_total_time)
        duration_layout.addWidget(self.duration_min)
        
        self.duration_sec = QSpinBox()
        self.duration_sec.setRange(0, 59)
        self.duration_sec.setValue(0)
        self.duration_sec.setSuffix(" sec")
        self.duration_sec.valueChanged.connect(self.update_total_time)
        duration_layout.addWidget(self.duration_sec)
        
        controls_layout.addWidget(duration_group)
        
        # Alert times group
        alerts_group = QGroupBox("Alert Times")
        alerts_layout = QVBoxLayout(alerts_group)
        
        # Enter room alert
        enter_frame = QWidget()
        enter_layout = QHBoxLayout(enter_frame)
        enter_layout.setContentsMargins(0, 0, 0, 0)
        
        self.enter_min = QSpinBox()
        self.enter_min.setRange(0, 60)
        self.enter_min.setValue(1)
        self.enter_min.setSuffix(" min")
        
        self.enter_sec = QSpinBox()
        self.enter_sec.setRange(0, 59)
        self.enter_sec.setValue(30)
        self.enter_sec.setSuffix(" sec")
        
        enter_layout.addWidget(QLabel("Enter room at:"))
        enter_layout.addWidget(self.enter_min)
        enter_layout.addWidget(self.enter_sec)
        alerts_layout.addWidget(enter_frame)
        
        # Sleep alert
        sleep_frame = QWidget()
        sleep_layout = QHBoxLayout(sleep_frame)
        sleep_layout.setContentsMargins(0, 0, 0, 0)
        
        self.sleep_min = QSpinBox()
        self.sleep_min.setRange(0, 60)
        self.sleep_min.setValue(7)
        self.sleep_min.setSuffix(" min")
        
        self.sleep_sec = QSpinBox()
        self.sleep_sec.setRange(0, 59)
        self.sleep_sec.setValue(30)
        self.sleep_sec.setSuffix(" sec")
        
        sleep_layout.addWidget(QLabel("Sleep at:"))
        sleep_layout.addWidget(self.sleep_min)
        sleep_layout.addWidget(self.sleep_sec)
        alerts_layout.addWidget(sleep_frame)
        
        # Auto-calculated alerts
        self.two_min_label = QLabel("Two minutes remaining: Auto (Duration - 2:00)")
        self.end_label = QLabel("End: Auto (At Duration)")
        
        alerts_layout.addWidget(self.two_min_label)
        alerts_layout.addWidget(self.end_label)
        
        controls_layout.addWidget(alerts_group)
        
        # Voice selection
        voice_group = QGroupBox("Voice Settings")
        voice_layout = QHBoxLayout(voice_group)
        
        self.voice_combo = QComboBox()
        self.voice_combo.addItems(self.voice_options)
        self.voice_combo.currentTextChanged.connect(self.update_voice)
        
        voice_layout.addWidget(QLabel("Voice:"))
        voice_layout.addWidget(self.voice_combo)
        
        controls_layout.addWidget(voice_group)
        
        # Volume control
        volume_layout = QHBoxLayout()
        volume_layout.addWidget(QLabel("Volume:"))
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(80)
        self.volume_slider.setFixedWidth(100)
        volume_layout.addWidget(self.volume_slider)
        controls_layout.addLayout(volume_layout)
        
        # Buttons
        button_style = """
            QPushButton {
                background-color: #007acc;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #005f9e;
            }
            QPushButton:disabled {
                background-color: #333333;
                color: #666666;
            }
        """
        
        self.start_button = QPushButton("Start")
        self.start_button.setStyleSheet(button_style)
        self.start_button.clicked.connect(self.start_timer)
        
        self.pause_button = QPushButton("Pause")
        self.pause_button.setStyleSheet(button_style)
        self.pause_button.setEnabled(False)
        self.pause_button.clicked.connect(self.pause_timer)
        
        self.reset_button = QPushButton("Reset")
        self.reset_button.setStyleSheet(button_style)
        self.reset_button.clicked.connect(self.reset_timer)
        
        self.test_button = QPushButton("Test Audio")
        self.test_button.setStyleSheet(button_style)
        self.test_button.clicked.connect(self.test_audio)
        
        # Add a debug button for TTS testing
        self.debug_button = QPushButton("Debug TTS")
        self.debug_button.setStyleSheet(button_style)
        self.debug_button.clicked.connect(self.debug_tts)
        
        # Add all buttons to layout
        controls_layout.addWidget(self.start_button)
        controls_layout.addWidget(self.pause_button)
        controls_layout.addWidget(self.reset_button)
        controls_layout.addWidget(self.test_button)
        controls_layout.addWidget(self.debug_button)
        
        layout.addLayout(controls_layout)
        
        # Set dark theme
        self.set_dark_theme()
        
        # Update the total time initially
        self.update_total_time()
    
    def set_dark_theme(self):
        # Set the application style and palette
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
            }
            QLabel {
                color: #d4d4d4;
            }
            QSpinBox, QComboBox {
                background-color: #333333;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                padding: 5px;
                border-radius: 4px;
            }
            QPushButton {
                background-color: #007acc;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #005f9e;
            }
            QPushButton:disabled {
                background-color: #333333;
                color: #666666;
            }
        """)
    
    def update_total_time(self):
        self.total_seconds = self.duration_min.value() * 60 + self.duration_sec.value()
        self.timeline.setMaximum(self.total_seconds)
        
        # Update alert times based on user input
        self.alert_times['enter_room'] = self.enter_min.value() * 60 + self.enter_sec.value()
        self.alert_times['sleep'] = self.sleep_min.value() * 60 + self.sleep_sec.value()
        self.alert_times['two_min_remaining'] = max(0, self.total_seconds - 120)
        self.alert_times['end'] = self.total_seconds
        
        # Update labels
        two_min_time = self.alert_times['two_min_remaining']
        two_min_str = f"{two_min_time // 60}:{two_min_time % 60:02d}"
        end_time_str = f"{self.total_seconds // 60}:{self.total_seconds % 60:02d}"
        
        self.two_min_label.setText(f"Two minutes remaining: Auto ({two_min_str})")
        self.end_label.setText(f"End: Auto ({end_time_str})")
        
        self.reset_timer()
    
    def update_voice(self, voice):
        self.current_voice = voice
        
    def set_fine_resolution(self):
        self.timeline.setSingleStep(10)  # 10 second steps for fine adjustment
    
    def set_coarse_resolution(self):
        self.timeline.setSingleStep(60)  # 1 minute steps for coarse adjustment
    
    def update_timer(self):
        if self.remaining_seconds > 0:
            self.remaining_seconds -= 1
            self.elapsed_seconds += 1
            self.update_display()
            self.check_alerts()
        else:
            self.timer.stop()
            self.running = False
            self.start_button.setEnabled(True)
            self.pause_button.setEnabled(False)
    
    def update_display(self):
        # Update timer display
        minutes = self.remaining_seconds // 60
        seconds = self.remaining_seconds % 60
        self.timer_label.setText(f"{minutes:02d}:{seconds:02d}")
        
        # Update elapsed time display
        elapsed_min = self.elapsed_seconds // 60
        elapsed_sec = self.elapsed_seconds % 60
        elapsed_str = f"Elapsed: {elapsed_min:02d}:{elapsed_sec:02d}"
        
        # Show current time in the timeline tooltip
        self.timeline.setToolTip(
            f"Drag to seek through the exam time\n"
            f"Current: {elapsed_min:02d}:{elapsed_sec:02d} / {self.total_seconds//60:02d}:{self.total_seconds%60:02d}\n"
            "Hover for fine adjustment (10s), move away for coarse (1m)"
        )
        
        self.elapsed_label.setText(elapsed_str)
        
        # Update timeline slider if user isn't dragging it
        if not self.timeline.isSliderDown():
            self.timeline.blockSignals(True)  # Prevent triggering valueChanged
            self.timeline.setValue(self.elapsed_seconds)
            self.timeline.blockSignals(False)
            
    def seek_timer(self, value):
        """Update timer position when the slider is moved"""
        # Update the timer position
        self.elapsed_seconds = value
        self.remaining_seconds = self.total_seconds - value
        
        # If we're running, we need to update the alerts
        if self.running:
            # Clear all alerts that would have been triggered after the new position
            self.alerts_triggered = {k for k, v in self.alert_times.items() 
                                   if v is not None and v <= self.elapsed_seconds}
            
            # Force check alerts to ensure we trigger any that should be active
            self.check_alerts(force_check=True)
        
        # Update the display
        self.update_display()
    def start_timer(self):
        if not self.running:
            if self.remaining_seconds == 0:
                # Reset alerts when starting fresh
                self.alerts_triggered.clear()
                self.remaining_seconds = self.total_seconds
                self.elapsed_seconds = 0
                self.timeline.setValue(0)
            
            self.running = True
            self.start_button.setEnabled(False)
            self.pause_button.setEnabled(True)
            self.timer.start(1000)  # Update every second
            
            # Update the timeline range
            self.timeline.setRange(0, self.total_seconds)
    
    def pause_timer(self):
        if self.running:
            self.timer.stop()
            self.running = False
            self.start_button.setEnabled(True)
            self.pause_button.setEnabled(False)
    
    def reset_timer(self):
        self.timer.stop()
        self.running = False
        self.remaining_seconds = 0
        self.elapsed_seconds = 0
        self.alerts_triggered.clear()
        self.timeline.setValue(0)
        self.update_display()
        self.start_button.setEnabled(True)
        self.pause_button.setEnabled(False)
        
        # Reset the timeline range
        self.timeline.setRange(0, self.total_seconds)
    
    def test_audio(self):
        threading.Thread(target=lambda: self.speak("This is a test of the text to speech system."), daemon=True).start()
        
    def debug_tts(self):
        """Debug function to test TTS with various texts"""
        test_texts = [
            "Test one two three.",
            "This is a longer test of the text to speech system.",
            "The quick brown fox jumps over the lazy dog."
        ]
        
        def play_next(index=0):
            if index < len(test_texts):
                self.speak(test_texts[index])
                # Schedule next text after a delay
                QTimer.singleShot(2000, lambda i=index+1: play_next(i))
        
        play_next()
    
    def speak(self, text):
        try:
            output_file = os.path.join(self.temp_dir, f"speech_{hash(text)}.mp3")
            
            if not os.path.exists(output_file):
                # Use the selected voice if available
                tts = gTTS(text=text, lang='en', tld='com')
                tts.save(output_file)
            
            # Stop any currently playing audio
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.fadeout(100)
                pygame.mixer.music.stop()
            
            # Set volume with boost (0.0 to 2.0 range)
            volume = (self.volume_slider.value() / 50.0)  # 200% max volume
            volume = min(max(volume, 0.0), 2.0)  # Clamp between 0 and 2.0
            
            # Initialize a new sound object for each playback
            sound = pygame.mixer.Sound(output_file)
            sound.set_volume(volume)
            
            # Play the audio in a non-blocking way
            channel = sound.play()
            
            # Keep a reference to the sound to prevent garbage collection
            if not hasattr(self, '_active_sounds'):
                self._active_sounds = []
            self._active_sounds.append((sound, channel))
            
            # Clean up finished sounds
            self._active_sounds = [(s, c) for s, c in self._active_sounds if c.get_busy()]
            
        except Exception as e:
            print(f"TTS Error: {e}")
            import traceback
            traceback.print_exc()
    
    def check_alerts(self, force_check=False):
        # If force_check is True, we're checking all alerts regardless of previous triggers
        if not force_check and not self.running:
            return
            
        # Check each alert
        alerts_to_check = [
            ('enter_room', "Enter the room"),
            ('sleep', "Sleep"),
            ('two_min_remaining', "Two minutes remaining"),
            ('end', "Time's up")
        ]
        
        for alert_key, alert_text in alerts_to_check:
            alert_time = self.alert_times.get(alert_key)
            if alert_time is None:
                continue
                
            # Check if we've passed this alert point
            if self.elapsed_seconds >= alert_time and (force_check or alert_key not in self.alerts_triggered):
                # If force_check is True, only trigger if we're at or past the alert time
                if force_check and self.elapsed_seconds < alert_time:
                    continue
                    
                # Only add to triggered if we're at the exact time (for non-force checks)
                if not force_check or self.elapsed_seconds == alert_time:
                    self.alerts_triggered.add(alert_key)
                
                # Always speak the alert if we're forcing or it's a new trigger
                if not force_check or alert_key not in self.alerts_triggered:
                    threading.Thread(target=lambda t=alert_text: self.speak(t), daemon=True).start()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle('Fusion')
    
    # Create and show the main window
    window = ExamTimer()
    window.show()
    
    # Run the application
    sys.exit(app.exec_())
