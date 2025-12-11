import sys
from qtpy import QtWidgets, QtGui, QtCore
from gtts import gTTS
import pygame
import os
import tempfile
import threading

class CustomSlider(QtWidgets.QSlider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.snap_points = []  # list of (point, color)

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.snap_points:
            return
        painter = QtGui.QPainter(self)
        min_val = self.minimum()
        max_val = self.maximum()
        width = self.width()
        height = self.height()
        for point, color in self.snap_points:
            if min_val <= point <= max_val:
                pos = (point - min_val) / (max_val - min_val) * width
                painter.setPen(QtGui.QPen(QtGui.QColor(color), 2))
                painter.drawLine(int(pos), height - 10, int(pos), height)

class ExamTimer(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Exam Timer with Audio Alerts")
        self.setFixedSize(600, 700)
        
        # Set dark theme colors (inspired by Visual Studio dark theme)
        self.bg_color = '#101010'  # Main background
        self.fg_color = '#e5e7eb'  # Text foreground
        self.accent_bg = '#111827'  # Widget background
        self.button_bg = '#2563eb'  # Accent blue for buttons
        self.button_fg = '#f9fafb'  # Button text
        self.active_bg = '#1d4ed8'  # Active button
        self.border_color = '#1f2937'  # Borders
        self.muted_fg = '#9ca3af'   # Muted text for italics
        
        # Alert colors
        self.alert_colors = {
            'begin': '#00FF00',  # green
            'enter_room': '#0000FF',  # blue
            'two_min_remaining': '#FFFF00',  # yellow
            'end': '#FF0000'  # red
        }
        
        # Set stylesheet for custom styles
        stylesheet = f"""
        QWidget {{
            background-color: {self.bg_color};
            color: {self.fg_color};
            font-family: 'Segoe UI', 'Arial';
            font-size: 10pt;
        }}
        QGroupBox {{
            border: 1px solid {self.border_color};
            border-radius: 10px;
            margin-top: 16px;
            background-color: {self.accent_bg};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 4px 10px;
            margin-left: 4px;
            color: {self.fg_color};
            font-weight: 600;
        }}
        QPushButton {{
            background-color: {self.button_bg};
            color: {self.button_fg};
            border-radius: 6px;
            border: 1px solid {self.border_color};
            padding: 6px 16px;
            font: 11pt 'Segoe UI';
        }}
        QPushButton:hover {{
            background-color: {self.active_bg};
        }}
        QPushButton:pressed {{
            background-color: {self.active_bg};
            border-color: {self.button_bg};
        }}
        QPushButton:disabled {{
            background-color: {self.accent_bg};
            color: {self.muted_fg};
            border-color: {self.border_color};
        }}
        QSpinBox, QComboBox {{
            background-color: {self.accent_bg};
            color: {self.fg_color};
            border-radius: 4px;
            border: 1px solid {self.border_color};
            padding: 4px 6px;
        }}
        QSpinBox:disabled, QComboBox:disabled {{
            background-color: {self.bg_color};
            color: {self.muted_fg};
        }}
        QSlider::groove:horizontal {{
            background: {self.accent_bg};
            border-radius: 4px;
            height: 8px;
            margin: 0 12px;
        }}
        QSlider::handle:horizontal {{
            background: {self.fg_color};
            border: 1px solid {self.border_color};
            width: 20px;
            margin: -6px 0;
            border-radius: 10px;
        }}
        QSlider::sub-page:horizontal {{
            background: #22c55e;
            border-radius: 4px;
        }}
        QSlider::add-page:horizontal {{
            background: #374151;
            border-radius: 4px;
        }}
        QFrame#timerFrame {{
            background-color: #020617;
            border-radius: 16px;
            border: 1px solid {self.border_color};
        }}
        QLabel {{
            color: {self.fg_color};
        }}
        """
        self.setStyleSheet(stylesheet)
        
        # Initialize pygame mixer for audio playback
        pygame.mixer.init()
        
        # Timer variables
        self.total_seconds = 9 * 60 + 30  # 9 minutes 30 seconds
        self.remaining_seconds = 0
        self.elapsed_seconds = 0
        self.running = False
        self.alerts_triggered = set()
        self.temp_dir = tempfile.mkdtemp()
        
        # Alert time points (in seconds from start)
        self.alert_times = {
            'begin': 0,  # 0:00 - Begin
            'enter_room': 90,  # 1:30 - Enter the room
            'two_min_remaining': None,  # Calculated dynamically - Two minutes remaining
            'end': None  # Calculated dynamically - Move to the next room
        }
        
        # Countdown timer
        self.countdown_timer = QtCore.QTimer()
        self.countdown_timer.timeout.connect(self.countdown)
        
        self.setup_ui()
        self.update_alert_times()

    def setup_ui(self):
        main_layout = QtWidgets.QVBoxLayout()
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)
        self.setLayout(main_layout)
        
        
        # Total duration input
        duration_group = QtWidgets.QGroupBox("Total Exam Duration")
        duration_layout = QtWidgets.QHBoxLayout()
        duration_group.setLayout(duration_layout)
        main_layout.addWidget(duration_group)
        
        min_label = QtWidgets.QLabel("Minutes:")
        min_label.setFont(QtGui.QFont('Segoe UI', 10))
        duration_layout.addWidget(min_label)
        
        self.duration_spin = QtWidgets.QSpinBox()
        self.duration_spin.setRange(1, 180)
        self.duration_spin.setValue(9)
        self.duration_spin.setFont(QtGui.QFont('Segoe UI', 11))
        self.duration_spin.valueChanged.connect(lambda _: self.update_alert_times())
        duration_layout.addWidget(self.duration_spin)
        
        sec_label = QtWidgets.QLabel("Seconds:")
        sec_label.setFont(QtGui.QFont('Segoe UI', 10))
        duration_layout.addWidget(sec_label)
        
        self.duration_sec_spin = QtWidgets.QSpinBox()
        self.duration_sec_spin.setRange(0, 59)
        self.duration_sec_spin.setValue(30)
        self.duration_sec_spin.setFont(QtGui.QFont('Segoe UI', 11))
        self.duration_sec_spin.valueChanged.connect(lambda _: self.update_alert_times())
        duration_layout.addWidget(self.duration_sec_spin)
        
        # Alert time points
        alerts_group = QtWidgets.QGroupBox("Alert Time Points")
        alerts_layout = QtWidgets.QGridLayout()
        alerts_group.setLayout(alerts_layout)
        main_layout.addWidget(alerts_group)
        
        # Begin alert
        alerts_layout.addWidget(QtWidgets.QLabel('1. "Begin" at:'), 0, 0)
        begin_italic = QtWidgets.QLabel("0:00 (Start)")
        begin_italic.setFont(QtGui.QFont('Segoe UI', 10, QtGui.QFont.StyleItalic))
        begin_italic.setStyleSheet(f"color: {self.muted_fg};")
        alerts_layout.addWidget(begin_italic, 0, 1)
        
        # Enter room alert
        alerts_layout.addWidget(QtWidgets.QLabel('2. "Enter the room" at:'), 1, 0)
        enter_frame = QtWidgets.QWidget()
        enter_hbox = QtWidgets.QHBoxLayout()
        enter_frame.setLayout(enter_hbox)
        self.enter_min_spin = QtWidgets.QSpinBox()
        self.enter_min_spin.setRange(0, 180)
        self.enter_min_spin.setValue(1)
        self.enter_min_spin.valueChanged.connect(lambda _: self.update_alert_times())
        enter_hbox.addWidget(self.enter_min_spin)
        enter_hbox.addWidget(QtWidgets.QLabel("min"))
        self.enter_sec_spin = QtWidgets.QSpinBox()
        self.enter_sec_spin.setRange(0, 59)
        self.enter_sec_spin.setValue(30)
        self.enter_sec_spin.valueChanged.connect(lambda _: self.update_alert_times())
        enter_hbox.addWidget(self.enter_sec_spin)
        enter_hbox.addWidget(QtWidgets.QLabel("sec"))
        alerts_layout.addWidget(enter_frame, 1, 1)
        
        # Two minutes remaining
        alerts_layout.addWidget(QtWidgets.QLabel('3. "Two minutes remaining":'), 2, 0)
        two_frame = QtWidgets.QWidget()
        two_hbox = QtWidgets.QHBoxLayout()
        two_frame.setLayout(two_hbox)
        self.two_min_min_spin = QtWidgets.QSpinBox()
        self.two_min_min_spin.setRange(0, 180)
        default_two_min = max(self.duration_spin.value() - 2, 0)
        self.two_min_min_spin.setValue(default_two_min)
        self.two_min_min_spin.valueChanged.connect(lambda _: self.update_alert_times())
        two_hbox.addWidget(self.two_min_min_spin)
        two_hbox.addWidget(QtWidgets.QLabel("min"))
        self.two_min_sec_spin = QtWidgets.QSpinBox()
        self.two_min_sec_spin.setRange(0, 59)
        self.two_min_sec_spin.setValue(self.duration_sec_spin.value())
        self.two_min_sec_spin.valueChanged.connect(lambda _: self.update_alert_times())
        two_hbox.addWidget(self.two_min_sec_spin)
        two_hbox.addWidget(QtWidgets.QLabel("sec"))
        alerts_layout.addWidget(two_frame, 2, 1)
        
        # End
        alerts_layout.addWidget(QtWidgets.QLabel('4. "Move to the next room":'), 3, 0)
        end_italic = QtWidgets.QLabel("Auto (At Duration)")
        end_italic.setFont(QtGui.QFont('Segoe UI', 10, QtGui.QFont.StyleItalic))
        end_italic.setStyleSheet(f"color: {self.muted_fg};")
        alerts_layout.addWidget(end_italic, 3, 1)
        
        # Voice selection
        voice_group = QtWidgets.QGroupBox("Voice Settings")
        voice_hbox = QtWidgets.QHBoxLayout()
        voice_group.setLayout(voice_hbox)
        main_layout.addWidget(voice_group)
        
        voice_label = QtWidgets.QLabel("Voice:")
        voice_label.setFont(QtGui.QFont('Segoe UI', 10))
        voice_hbox.addWidget(voice_label)
        
        self.voice_combo = QtWidgets.QComboBox()
        self.voice_combo.addItems([
            "en-US-AriaNeural",
            "en-US-GuyNeural",
            "en-US-JennyNeural",
            "en-GB-RyanNeural",
            "en-GB-SoniaNeural"
        ])
        self.voice_combo.setCurrentText("en-US-AriaNeural")
        voice_hbox.addWidget(self.voice_combo)
        
        # Volume control
        volume_group = QtWidgets.QGroupBox("Volume Control")
        volume_vbox = QtWidgets.QVBoxLayout()
        volume_group.setLayout(volume_vbox)
        main_layout.addWidget(volume_group)
        
        self.volume_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.volume_slider.setRange(0, 200)
        self.volume_slider.setValue(150)
        self.volume_slider.valueChanged.connect(self.update_volume)
        volume_vbox.addWidget(self.volume_slider)
        
        self.volume_label = QtWidgets.QLabel("Volume: 150%")
        self.volume_label.setFont(QtGui.QFont('Segoe UI', 10))
        volume_vbox.addWidget(self.volume_label, alignment=QtCore.Qt.AlignCenter)
        
        test_button = QtWidgets.QPushButton("Test Audio")
        test_button.clicked.connect(self.test_audio)
        volume_vbox.addWidget(test_button)
        
        # Timer display
        self.timer_label = QtWidgets.QLabel("00:00")
        self.timer_label.setFont(QtGui.QFont('Segoe UI', 48, QtGui.QFont.Bold))
        self.timer_label.setStyleSheet("color: #22c55e;")
        main_layout.addWidget(self.timer_label, alignment=QtCore.Qt.AlignCenter)
        
        self.elapsed_label = QtWidgets.QLabel("Elapsed: 00:00")
        self.elapsed_label.setFont(QtGui.QFont('Segoe UI', 11))
        self.elapsed_label.setStyleSheet(f"color: {self.muted_fg};")
        main_layout.addWidget(self.elapsed_label, alignment=QtCore.Qt.AlignCenter)
        
        # Time progress bar (slider)
        self.time_slider = CustomSlider(QtCore.Qt.Horizontal)
        self.time_slider.setRange(0, 9 * 60 + 30)  # Default to 9 minutes 30 seconds
        self.time_slider.setValue(0)
        self.time_slider.setSingleStep(60)
        self.time_slider.valueChanged.connect(self.update_from_slider)
        self.time_slider.sliderReleased.connect(self.snap_to_key)
        main_layout.addWidget(self.time_slider)
        
        def enter_event(event):
            self.time_slider.setSingleStep(5)
        
        def leave_event(event):
            self.time_slider.setSingleStep(60)
        
        self.time_slider.enterEvent = enter_event
        self.time_slider.leaveEvent = leave_event
        
        # Buttons frame
        button_hbox = QtWidgets.QHBoxLayout()
        button_hbox.setSpacing(16)
        main_layout.addLayout(button_hbox)
        button_hbox.addStretch(1)
        
        self.start_button = QtWidgets.QPushButton("Start")
        self.start_button.clicked.connect(self.start_timer)
        button_hbox.addWidget(self.start_button)
        
        self.pause_button = QtWidgets.QPushButton("Pause")
        self.pause_button.clicked.connect(self.pause_timer)
        self.pause_button.setEnabled(False)
        button_hbox.addWidget(self.pause_button)
        
        self.reset_button = QtWidgets.QPushButton("Reset")
        self.reset_button.clicked.connect(self.reset_timer)
        button_hbox.addWidget(self.reset_button)
        button_hbox.addStretch(1)
        
    def snap_to_key(self):
        current = self.time_slider.value()
        snap_points = [p for p, c in self.time_slider.snap_points]
        if snap_points:
            closest = min(snap_points, key=lambda x: abs(x - current))
            if abs(current - closest) < 15:  # snap threshold in seconds
                self.time_slider.setValue(closest)
                self.slider_moved = True
                self.update_from_slider(closest)
    
    def update_volume(self, value):
        self.volume_label.setText(f"Volume: {value}%")
        volume = value / 100.0
        pygame.mixer.music.set_volume(volume)
    
    def test_audio(self):
        threading.Thread(target=lambda: self.speak("Test audio"), daemon=True).start()
    
    def generate_speech(self, text):
        """Generate speech using gTTS"""
        output_file = os.path.join(self.temp_dir, f"speech_{hash(text)}.mp3")
        
        if not os.path.exists(output_file):
            lang = 'en'
            tld = 'com'  # Default US accent
            if 'GB' in self.voice_combo.currentText():
                tld = 'co.uk'  # UK accent
            tts = gTTS(text, lang=lang, tld=tld)
            tts.save(output_file)
        
        return output_file
    
    def speak(self, text):
        """Play speech using pygame mixer"""
        try:
            audio_file = self.generate_speech(text)
            
            # Play audio
            pygame.mixer.music.load(audio_file)
            volume = self.volume_slider.value() / 100.0
            pygame.mixer.music.set_volume(volume)
            pygame.mixer.music.play()
            
            # Wait for audio to finish
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
                
        except Exception as e:
            print(f"TTS Error: {e}")
    
    def update_alert_times(self):
        # Get duration from spin boxes
        minutes = self.duration_spin.value()
        seconds = self.duration_sec_spin.value()
        self.total_seconds = minutes * 60 + seconds
        
        # Get enter room time
        enter_min = self.enter_min_spin.value()
        enter_sec = self.enter_sec_spin.value()
        self.alert_times['enter_room'] = enter_min * 60 + enter_sec
        
        # Set two minutes remaining and end times
        two_min_total = self.two_min_min_spin.value() * 60 + self.two_min_sec_spin.value()
        self.alert_times['two_min_remaining'] = two_min_total
        self.alert_times['end'] = self.total_seconds
        
        # Update slider max and snap points
        self.time_slider.setMaximum(self.total_seconds)
        self.time_slider.snap_points = [(time, self.alert_colors[key]) for key, time in self.alert_times.items() if time is not None]
        self.time_slider.update()
        
        return True
    
    def start_timer(self):
        if self.running:
            return

        try:
            # Determine whether this is a fresh start or a resume
            is_resume = self.elapsed_seconds > 0 and self.remaining_seconds > 0

            if not is_resume:
                # Update alert times first
                if not self.update_alert_times():
                    return

                if self.total_seconds <= 0:
                    QtWidgets.QMessageBox.warning(self, "Invalid Duration", "Duration must be greater than 0")
                    return

                # Validate alert times
                if self.alert_times['enter_room'] >= self.total_seconds:
                    QtWidgets.QMessageBox.warning(self, "Invalid Alert Time", "Enter room time must be before exam end")
                    return

                if (
                    self.alert_times['two_min_remaining'] is not None
                    and self.alert_times['two_min_remaining'] >= self.total_seconds
                ):
                    QtWidgets.QMessageBox.warning(
                        self,
                        "Invalid Alert Time",
                        '"Two minutes remaining" time must be before exam end',
                    )
                    return

                self.remaining_seconds = self.total_seconds
                self.elapsed_seconds = 0
                self.alerts_triggered.clear()
                self.update_labels()
                self.time_slider.setMaximum(self.total_seconds)
                self.time_slider.setValue(0)

                # Trigger "Begin" alert only on a fresh start
                threading.Thread(target=lambda: self.speak("Begin"), daemon=True).start()
                self.alerts_triggered.add('begin')

            self.running = True
            self.start_button.setText("Start")
            self.start_button.setEnabled(False)
            self.pause_button.setEnabled(True)
            self.disable_inputs()
            self.countdown_timer.start(1000)  # Update every second

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")
            return
    
    def pause_timer(self):
        if self.running:
            self.running = False
            self.start_button.setText("Resume")
            self.start_button.setEnabled(True)
            self.pause_button.setEnabled(False)
            self.countdown_timer.stop()
    
    def reset_timer(self):
        self.running = False
        self.remaining_seconds = 0
        self.elapsed_seconds = 0
        self.alerts_triggered.clear()
        self.timer_label.setText("00:00")
        self.elapsed_label.setText("Elapsed: 00:00")
        self.time_slider.setValue(0)
        self.time_slider.setMaximum(0)
        self.time_slider.snap_points = []
        self.time_slider.update()
        self.start_button.setText("Start")
        self.start_button.setEnabled(True)
        self.pause_button.setEnabled(False)
        self.enable_inputs()
        self.countdown_timer.stop()
    
    def disable_inputs(self):
        self.duration_spin.setEnabled(False)
        self.duration_sec_spin.setEnabled(False)
        self.enter_min_spin.setEnabled(False)
        self.enter_sec_spin.setEnabled(False)
        # Keep the time_slider enabled to allow seeking during timer
        self.time_slider.setEnabled(True)
    
    def enable_inputs(self):
        self.duration_spin.setEnabled(True)
        self.duration_sec_spin.setEnabled(True)
        self.enter_min_spin.setEnabled(True)
        self.enter_sec_spin.setEnabled(True)
        self.time_slider.setEnabled(True)
    
    def check_alerts(self):
        # Check each alert and trigger TTS when passing time points
        current_time = self.elapsed_seconds
        
        # Check if we've passed the 'enter_room' time point
        if (
            'enter_room' not in self.alerts_triggered
            and self.alert_times['enter_room'] is not None
            and current_time >= self.alert_times['enter_room']
        ):
            threading.Thread(target=lambda: self.speak("Enter the room"), daemon=True).start()
            self.alerts_triggered.add('enter_room')
        
        # Check if we've passed the 'two_min_remaining' time point
        if (
            'two_min_remaining' not in self.alerts_triggered
            and self.alert_times['two_min_remaining'] is not None
            and current_time >= self.alert_times['two_min_remaining']
        ):
            threading.Thread(target=lambda: self.speak("Two minutes remaining"), daemon=True).start()
            self.alerts_triggered.add('two_min_remaining')
            
        # Update the last alert time for the next check
        self.last_alert_time = current_time
    
    def update_from_slider(self, value):
        # Store the previous time to check if we're moving forward or backward
        prev_time = getattr(self, 'elapsed_seconds', 0)
        self.elapsed_seconds = value
        self.remaining_seconds = self.total_seconds - self.elapsed_seconds
        
        # Check alerts when slider moves
        self.check_alerts()
        self.update_labels()
    
    def update_labels(self):
        minutes = self.remaining_seconds // 60
        seconds = self.remaining_seconds % 60
        time_str = f"{minutes:02d}:{seconds:02d}"
        self.timer_label.setText(time_str)
        
        elapsed_min = self.elapsed_seconds // 60
        elapsed_sec = self.elapsed_seconds % 60
        elapsed_str = f"Elapsed: {elapsed_min:02d}:{elapsed_sec:02d}"
        self.elapsed_label.setText(elapsed_str)
    
    def countdown(self):
        if self.running and self.remaining_seconds > 0:
            # Store the previous time before updating
            prev_time = self.elapsed_seconds
            self.remaining_seconds -= 1
            self.elapsed_seconds += 1
            # Only check alerts if time is moving forward naturally (not from slider)
            if not hasattr(self, 'slider_moved') or not self.slider_moved:
                self.check_alerts()
            self.slider_moved = False           
            self.time_slider.setValue(self.elapsed_seconds)
            self.update_labels()
            
        elif self.running and self.remaining_seconds == 0:
            self.timer_label.setText("00:00")
            self.running = False
            self.start_button.setText("Start")
            self.start_button.setEnabled(True)
            self.pause_button.setEnabled(False)
            self.enable_inputs()
            self.countdown_timer.stop()
            
            if 'end' not in self.alerts_triggered:
                threading.Thread(target=lambda: self.speak("Move to the next room"), daemon=True).start()
                self.alerts_triggered.add('end')

def apply_dark_theme(app):
    palette = QtGui.QPalette()
    palette.setColor(QtGui.QPalette.Window, QtGui.QColor(30, 30, 30))
    palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor(212, 212, 212))
    palette.setColor(QtGui.QPalette.Base, QtGui.QColor(51, 51, 51))
    palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(30, 30, 30))
    palette.setColor(QtGui.QPalette.ToolTipBase, QtGui.QColor(212, 212, 212))
    palette.setColor(QtGui.QPalette.ToolTipText, QtGui.QColor(212, 212, 212))
    palette.setColor(QtGui.QPalette.Text, QtGui.QColor(212, 212, 212))
    palette.setColor(QtGui.QPalette.Button, QtGui.QColor(51, 51, 51))
    palette.setColor(QtGui.QPalette.ButtonText, QtGui.QColor(212, 212, 212))
    palette.setColor(QtGui.QPalette.BrightText, QtCore.Qt.red)
    palette.setColor(QtGui.QPalette.Link, QtGui.QColor(42, 130, 218))
    palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor(0, 122, 204))
    palette.setColor(QtGui.QPalette.HighlightedText, QtCore.Qt.white)
    app.setPalette(palette)

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle('Fusion')
    apply_dark_theme(app)
    window = ExamTimer()
    window.show()
    sys.exit(app.exec_())