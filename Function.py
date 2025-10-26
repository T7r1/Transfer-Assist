import sys
import os
import json
import csv
import io
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QComboBox, QLineEdit, QListWidget, QListWidgetItem, QSplitter, QTextEdit, 
    QPushButton, QMessageBox, QSpinBox, QTableWidget, QTableWidgetItem, 
    QAbstractItemView, QFileDialog, QProgressBar
)
import anthropic
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ==================== ENVIRONMENT & CONFIG ====================

def load_env_from_script_dir():
    """Load API key from .env files in script directory"""
    here = Path(__file__).resolve().parent
    for name in (".env", "ANTHROPIC_API_KEY.env"):
        p = here / name
        if p.exists():
            load_dotenv(dotenv_path=p, override=True)
            return
    load_dotenv(override=False)

# ==================== AI WORKER THREAD ====================

class ClaudeWorker(QThread):
    response_received = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    progress_updated = pyqtSignal(str)

    def __init__(self, api_key: str, model: str, messages: list[dict], max_tokens: int):
        super().__init__()
        self.api_key = api_key
        self.model = model
        self.messages = messages
        self.max_tokens = max_tokens

    def run(self):
        try:
            self.progress_updated.emit("Connecting to Claude...")
            client = anthropic.Anthropic(api_key=self.api_key)
            
            self.progress_updated.emit("Generating response...")
            resp = client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=self.messages
            )
            
            text = ""
            if getattr(resp, "content", None):
                parts = []
                for blk in resp.content:
                    if getattr(blk, "type", "") == "text":
                        parts.append(blk.text)
                text = "\n".join(parts).strip()
            
            self.progress_updated.emit("Response received")
            self.response_received.emit(text or "[empty response]")
            
        except Exception as e:
            self.progress_updated.emit("Error occurred")
            self.error_occurred.emit(str(e))

# ==================== DATA MANAGEMENT ====================

class UniversityDataManager:
    """Handles university and course data operations"""
    
    @staticmethod
    def load_universities(json_path: Path):
        """Load university data from JSON file"""
        if not json_path.exists():
            return {
                "universities": [
                    {"name": "UC Berkeley", "majors": ["EECS", "ME", "Physics"], "system": "UC"},
                    {"name": "Caltech", "majors": ["EE", "ME", "CS"], "system": "Private"},
                    {"name": "Los Angeles City College", "majors": ["Math", "Science", "Arts"], "system": "CCC"}
                ]
            }
        
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        if isinstance(data, list):
            return {"universities": data}
        if isinstance(data, dict) and isinstance(data.get("universities"), list):
            return data
        return {"universities": [data]}

    @staticmethod
    def get_university_names(uni_data):
        """Extract university names from data"""
        return [u.get("name", "") for u in uni_data.get("universities", []) 
                if isinstance(u, dict) and u.get("name")]

    @staticmethod
    def get_majors_by_university(uni_data):
        """Create mapping of university to majors"""
        return {u.get("name", ""): u.get("majors", []) 
                for u in uni_data.get("universities", []) 
                if isinstance(u, dict)}

    @staticmethod
    def get_system_by_university(uni_data):
        """Create mapping of university to system"""
        return {u.get("name", ""): u.get("system", "Unknown")
                for u in uni_data.get("universities", [])
                if isinstance(u, dict)}

# ==================== COURSE CATALOG ====================

class CourseCatalog:
    """Manages course catalog and planning data"""
    
    def __init__(self):
        self.courses = {
            'current_school': [],
            'target_school': []
        }
        self.transfer_plan = []
        self.gantt_data = []
    
    def generate_gantt_data(self, planned_courses, transfer_date):
        """Generate data for Gantt chart visualization"""
        gantt_data = []
        current_date = datetime.now()
        
        # Current school courses
        for i, course in enumerate(planned_courses):
            start_date = current_date + timedelta(weeks=i * 16)
            end_date = start_date + timedelta(weeks=16)
            gantt_data.append({
                'Task': course,
                'Start': start_date,
                'Finish': end_date,
                'Institution': 'Current School',
                'Resource': 'Current'
            })
        
        # Transfer milestone
        gantt_data.append({
            'Task': 'TRANSFER',
            'Start': transfer_date,
            'Finish': transfer_date + timedelta(days=7),
            'Institution': 'Transfer',
            'Resource': 'Transfer'
        })
        
        return gantt_data

# ==================== DRAG & DROP LISTS ====================

class DragList(QListWidget):
    """List widget that supports dragging items"""
    def __init__(self):
        super().__init__()
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)

# ==================== MAIN APPLICATION ====================

class TransferPlannerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.api_key = None
        self.worker = None
        self.history = []
        
        # Initialize data managers
        self.data_manager = UniversityDataManager()
        self.course_catalog = CourseCatalog()
        
        # Load university data
        self.uni_data = self.data_manager.load_universities(
            Path(__file__).resolve().parent / "university.json"
        )
        
        self.init_ui()
        self.apply_dark_theme()

    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("Transfer Assist — AI-Powered Course Planner")
        self.resize(1400, 900)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Top controls
        self.create_top_controls(main_layout)
        
        # Main content area
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter, 1)
        
        # Left panel - Course planning
        left_panel = self.create_left_panel()
        splitter.addWidget(left_panel)
        
        # Center panel - Schedule grid
        center_panel = self.create_center_panel()
        splitter.addWidget(center_panel)
        
        # Right panel - AI assistant
        right_panel = self.create_right_panel()
        splitter.addWidget(right_panel)
        
        splitter.setSizes([400, 600, 400])
        
        self.statusBar().showMessage("Ready to plan your transfer journey!")

    def create_top_controls(self, parent_layout):
        """Create top control bar"""
        top_layout = QHBoxLayout()
        
        # Model selection
        top_layout.addWidget(QLabel("AI Model:"))
        self.model_combo = QComboBox()
        self.model_combo.addItems([
            "claude-3-haiku-20240307", 
            "claude-3-sonnet-20240229", 
            "claude-3-opus-20240229"
        ])
        top_layout.addWidget(self.model_combo)
        
        # Token control
        top_layout.addWidget(QLabel("Max tokens:"))
        self.max_tokens = QSpinBox()
        self.max_tokens.setRange(200, 4000)
        self.max_tokens.setValue(1200)
        top_layout.addWidget(self.max_tokens)
        
        # Action buttons
        load_btn = QPushButton("Load University Data")
        load_btn.clicked.connect(self.load_university_data)
        top_layout.addWidget(load_btn)
        
        export_btn = QPushButton("Export Plan")
        export_btn.clicked.connect(self.export_plan)
        top_layout.addWidget(export_btn)
        
        gantt_btn = QPushButton("View Gantt Chart")
        gantt_btn.clicked.connect(self.show_gantt_chart)
        top_layout.addWidget(gantt_btn)
        
        top_layout.addStretch()
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        top_layout.addWidget(self.progress_bar)
        
        parent_layout.addLayout(top_layout)

    def create_left_panel(self):
        """Create left panel with university and course controls"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # University selection
        layout.addWidget(self.create_section_label("University Selection"))
        
        layout.addWidget(QLabel("Current University:"))
        self.current_uni = QComboBox()
        self.current_uni.addItems(self.data_manager.get_university_names(self.uni_data))
        self.current_uni.currentTextChanged.connect(self.on_university_change)
        layout.addWidget(self.current_uni)
        
        layout.addWidget(QLabel("Target University:"))
        self.target_uni = QComboBox()
        self.target_uni.addItems(self.data_manager.get_university_names(self.uni_data))
        self.target_uni.currentTextChanged.connect(self.on_university_change)
        layout.addWidget(self.target_uni)
        
        layout.addWidget(QLabel("Major:"))
        self.major = QComboBox()
        self.major.setEditable(True)
        self.update_majors_list()
        layout.addWidget(self.major)
        
        # Term selection
        layout.addWidget(self.create_section_label("Academic Term"))
        term_layout = QHBoxLayout()
        self.term = QComboBox()
        self.term.addItems(["Fall", "Spring", "Summer"])
        term_layout.addWidget(self.term)
        
        self.term_year = QSpinBox()
        self.term_year.setRange(2000, 2100)
        self.term_year.setValue(datetime.now().year)
        term_layout.addWidget(self.term_year)
        layout.addLayout(term_layout)
        
        # Course lists
        layout.addWidget(self.create_section_label("Course Planning"))
        
        layout.addWidget(QLabel("Available Courses:"))
        self.available_courses = DragList()
        self.populate_sample_courses()
        layout.addWidget(self.available_courses)
        
        layout.addWidget(QLabel("Planned Courses:"))
        self.planned_courses = DragList()
        layout.addWidget(self.planned_courses)
        
        # Custom course addition
        custom_layout = QHBoxLayout()
        self.custom_course_input = QLineEdit()
        self.custom_course_input.setPlaceholderText("Add custom course...")
        custom_layout.addWidget(self.custom_course_input)
        
        add_course_btn = QPushButton("Add")
        add_course_btn.clicked.connect(self.add_custom_course)
        custom_layout.addWidget(add_course_btn)
        layout.addLayout(custom_layout)
        
        # Action buttons
        suggest_schedule_btn = QPushButton("Suggest Weekly Schedule")
        suggest_schedule_btn.clicked.connect(self.suggest_weekly_schedule)
        layout.addWidget(suggest_schedule_btn)
        
        suggest_courses_btn = QPushButton("AI: Suggest Missing Courses")
        suggest_courses_btn.clicked.connect(self.ai_suggest_courses)
        layout.addWidget(suggest_courses_btn)
        
        generate_plan_btn = QPushButton("AI: Generate Transfer Plan")
        generate_plan_btn.clicked.connect(self.ai_generate_plan)
        layout.addWidget(generate_plan_btn)
        
        commit_btn = QPushButton("🎯 I'm Committed - Start Journey")
        commit_btn.setStyleSheet("background: #e74c3c; color: white; font-weight: bold; padding: 10px;")
        commit_btn.clicked.connect(self.commit_to_journey)
        layout.addWidget(commit_btn)
        
        return panel

    def create_center_panel(self):
        """Create center panel with schedule grid and script"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Weekly schedule grid
        layout.addWidget(self.create_section_label("Weekly Schedule Grid"))
        self.schedule_grid = QTableWidget(12, 5)
        self.setup_schedule_grid()
        layout.addWidget(self.schedule_grid, 2)
        
        # Schedule script
        layout.addWidget(self.create_section_label("Transfer Plan Script"))
        self.script_display = QTextEdit()
        self.script_display.setReadOnly(True)
        layout.addWidget(self.script_display, 1)
        
        return panel

    def create_right_panel(self):
        """Create right panel with AI assistant"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        layout.addWidget(self.create_section_label("AI Transfer Assistant"))
        
        layout.addWidget(QLabel("Your Question:"))
        self.user_prompt_input = QTextEdit()
        self.user_prompt_input.setPlaceholderText(
            "Ask about transfer requirements, course sequencing, schedule optimization..."
        )
        layout.addWidget(self.user_prompt_input)
        
        send_ai_btn = QPushButton("Send to AI Assistant")
        send_ai_btn.clicked.connect(self.send_to_ai)
        layout.addWidget(send_ai_btn)
        
        layout.addWidget(QLabel("AI Response:"))
        self.ai_response_display = QTextEdit()
        self.ai_response_display.setReadOnly(True)
        layout.addWidget(self.ai_response_display, 2)
        
        return panel

    def create_section_label(self, text):
        """Create a styled section label"""
        label = QLabel(text)
        label.setStyleSheet("font-weight: bold; font-size: 14px; padding: 8px 0px; color: #3498db;")
        return label

    def setup_schedule_grid(self):
        """Setup the weekly schedule grid"""
        self.schedule_grid.setHorizontalHeaderLabels(["Mon", "Tue", "Wed", "Thu", "Fri"])
        self.schedule_grid.setVerticalHeaderLabels([f"{h:02d}:00" for h in range(8, 20)])
        self.schedule_grid.verticalHeader().setDefaultSectionSize(30)
        self.schedule_grid.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

    def populate_sample_courses(self):
        """Populate with sample courses"""
        sample_courses = [
            "Calculus I", "Calculus II", "Linear Algebra", "Physics I", "Physics II",
            "General Chemistry", "Organic Chemistry", "Biology", "Computer Science I",
            "Data Structures", "Algorithms", "Discrete Mathematics", "Statistics",
            "English Composition", "Psychology", "Economics", "History"
        ]
        for course in sample_courses:
            QListWidgetItem(course, self.available_courses)

    def apply_dark_theme(self):
        """Apply dark theme styling"""
        self.setStyleSheet("""
            QMainWindow {
                background: #1e1e1e;
                color: #e0e0e0;
            }
            QLabel {
                color: #e0e0e0;
            }
            QTextEdit, QLineEdit, QComboBox, QSpinBox {
                background: #2d2d2d;
                color: #e0e0e0;
                border: 1px solid #404040;
                border-radius: 4px;
                padding: 6px;
            }
            QListWidget, QTableWidget {
                background: #252525;
                color: #e0e0e0;
                border: 1px solid #404040;
                border-radius: 4px;
            }
            QPushButton {
                background: #27ae60;
                color: white;
                border: none;
                padding: 8px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #219653;
            }
            QHeaderView::section {
                background: #34495e;
                color: white;
                padding: 6px;
                border: none;
            }
            QProgressBar {
                border: 1px solid #404040;
                border-radius: 4px;
                text-align: center;
                color: white;
            }
            QProgressBar::chunk {
                background: #3498db;
                border-radius: 3px;
            }
        """)

    # ==================== EVENT HANDLERS ====================

    def on_university_change(self):
        """Handle university selection changes"""
        self.update_majors_list()
        self.update_script_display()

    def update_majors_list(self):
        """Update majors list based on selected universities"""
        self.major.clear()
        majors_map = self.data_manager.get_majors_by_university(self.uni_data)
        
        # Combine majors from both current and target universities
        current_uni = self.current_uni.currentText()
        target_uni = self.target_uni.currentText()
        
        all_majors = set()
        if current_uni in majors_map:
            all_majors.update(majors_map[current_uni])
        if target_uni in majors_map:
            all_majors.update(majors_map[target_uni])
        
        self.major.addItems(sorted(all_majors))

    def add_custom_course(self):
        """Add custom course to available courses"""
        course_name = self.custom_course_input.text().strip()
        if course_name:
            QListWidgetItem(course_name, self.available_courses)
            self.custom_course_input.clear()
            self.statusBar().showMessage(f"Added course: {course_name}")

    def suggest_weekly_schedule(self):
        """Generate a suggested weekly schedule"""
        planned = [self.planned_courses.item(i).text() 
                  for i in range(self.planned_courses.count())]
        
        if not planned:
            QMessageBox.information(self, "No Courses", 
                                  "Please add courses to your planned list first.")
            return
        
        # Clear existing schedule
        for row in range(self.schedule_grid.rowCount()):
            for col in range(self.schedule_grid.columnCount()):
                self.schedule_grid.setItem(row, col, QTableWidgetItem(""))
        
        # Simple scheduling algorithm
        hour = 9  # Start at 9 AM
        for i, course in enumerate(planned):
            day = i % 4  # Spread across Mon-Thu
            row = hour - 8  # Convert to row index
            
            if row < self.schedule_grid.rowCount():
                self.schedule_grid.setItem(row, day, QTableWidgetItem(course))
            
            hour += 2  # Move to next time slot
            if hour >= 19:  # Reset if beyond 7 PM
                hour = 9
        
        self.update_script_display()
        self.statusBar().showMessage("Weekly schedule generated")

    def update_script_display(self):
        """Update the plan script display"""
        current_uni = self.current_uni.currentText()
        target_uni = self.target_uni.currentText()
        major = self.major.currentText()
        term = f"{self.term.currentText()} {self.term_year.value()}"
        
        planned = [self.planned_courses.item(i).text() 
                  for i in range(self.planned_courses.count())]
        
        script = f"""TRANSFER PLANNING SCRIPT
=======================

Academic Plan for {term}
Current: {current_uni} → Target: {target_uni}
Major: {major}

PLANNED COURSES:
{chr(10).join(f"• {course}" for course in planned) if planned else "• No courses planned yet"}

STRATEGY:
• Complete prerequisite courses for {target_uni}
• Maintain strong GPA (target: 3.5+)
• Meet with transfer counselor regularly
• Complete application by deadline

WEEKLY SCHEDULE:
• Balance STEM and GE courses
• Reserve time for study groups
• Include office hours attendance
"""
        self.script_display.setPlainText(script)

    # ==================== AI INTEGRATION ====================

    def ensure_api_key(self):
        """Ensure API key is available"""
        if self.api_key:
            return True
        
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            QMessageBox.critical(self, "API Key Required",
                               "Please set ANTHROPIC_API_KEY in your environment variables or .env file.")
            return False
        return True

    def build_ai_context(self):
        """Build context for AI requests"""
        current_uni = self.current_uni.currentText()
        target_uni = self.target_uni.currentText()
        major = self.major.currentText()
        term = f"{self.term.currentText()} {self.term_year.value()}"
        
        planned_courses = [self.planned_courses.item(i).text() 
                          for i in range(self.planned_courses.count())]
        available_courses = [self.available_courses.item(i).text() 
                            for i in range(self.available_courses.count())]
        
        systems_map = self.data_manager.get_system_by_university(self.uni_data)
        current_system = systems_map.get(current_uni, "Unknown")
        target_system = systems_map.get(target_uni, "Unknown")
        
        return f"""
[TRANSFER_STUDENT_CONTEXT]
current_university={current_uni}
current_system={current_system}
target_university={target_uni}  
target_system={target_system}
major={major}
current_term={term}
planned_courses={'; '.join(planned_courses)}
available_courses={'; '.join(available_courses)}
today_date={datetime.now().strftime('%Y-%m-%d')}

RESPONSE_FORMAT=CSV_AND_TEXT
CSV_COLUMNS=Course,Term,Priority,Credits,DurationWeeks,Notes
TERM_FORMATS=Fall 2024,Spring 2025,Summer 2025,Fall 2025
PRIORITY_LEVELS=High,Medium,Low
[/TRANSFER_STUDENT_CONTEXT]

Please provide:
1. Detailed text advice in 'text_suggestion: {{...}}' format
2. CSV course plan in 'code: {{...}}' format
"""

    def send_to_ai(self):
        """Send user prompt to AI"""
        user_prompt = self.user_prompt_input.toPlainText().strip()
        if not user_prompt:
            QMessageBox.warning(self, "Empty Prompt", "Please enter a question for the AI.")
            return
        
        if not self.ensure_api_key():
            return
        
        context = self.build_ai_context()
        full_prompt = context + "\n\n" + user_prompt
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        
        self.history.append({"role": "user", "content": full_prompt})
        self.ai_response_display.append("🔷 You: " + user_prompt + "\n")
        
        self.worker = ClaudeWorker(
            self.api_key,
            self.model_combo.currentText(),
            self.history,
            self.max_tokens.value()
        )
        self.worker.response_received.connect(self.handle_ai_response)
        self.worker.error_occurred.connect(self.handle_ai_error)
        self.worker.progress_updated.connect(self.update_progress)
        self.worker.start()

    def ai_suggest_courses(self):
        """AI suggests missing courses for transfer"""
        prompt = "Based on my current situation, what courses are missing from my plan that I should take to strengthen my transfer application? Focus on prerequisites and recommended courses for my target university and major."
        self.user_prompt_input.setPlainText(prompt)
        self.send_to_ai()

    def ai_generate_plan(self):
        """AI generates comprehensive transfer plan"""
        prompt = "Create a comprehensive transfer plan including course sequencing across multiple terms, prerequisite planning, and strategic advice for successful transfer admission."
        self.user_prompt_input.setPlainText(prompt)
        self.send_to_ai()

    def handle_ai_response(self, response):
        """Handle AI response"""
        self.progress_bar.setVisible(False)
        
        # Try to parse CSV from response
        if self.parse_ai_csv_response(response):
            self.ai_response_display.append("✅ Course plan imported successfully!\n")
        else:
            self.ai_response_display.append("🤖 Claude: " + response + "\n")
        
        self.history.append({"role": "assistant", "content": response})
        self.update_script_display()

    def handle_ai_error(self, error):
        """Handle AI error"""
        self.progress_bar.setVisible(False)
        self.ai_response_display.append(f"❌ Error: {error}\n")
        self.statusBar().showMessage(f"AI Error: {error}")

    def update_progress(self, message):
        """Update progress bar message"""
        self.statusBar().showMessage(message)

    def parse_ai_csv_response(self, response):
        """Parse CSV data from AI response and update UI"""
        try:
            # Extract CSV from response
            if "code: {" in response:
                start_idx = response.find("code: {") + 7
                end_idx = response.find("}", start_idx)
                csv_text = response[start_idx:end_idx].strip()
            else:
                # Look for CSV format in response
                lines = response.split('\n')
                csv_lines = []
                in_csv = False
                
                for line in lines:
                    if any(x in line for x in ['Course,', 'course,']):
                        in_csv = True
                    if in_csv and line.strip():
                        csv_lines.append(line.strip())
                    if in_csv and not line.strip():
                        break
                
                if csv_lines:
                    csv_text = '\n'.join(csv_lines)
                else:
                    return False
            
            # Parse CSV
            reader = csv.DictReader(io.StringIO(csv_text))
            course_plan = list(reader)
            
            if not course_plan:
                return False
            
            # Clear existing planned courses
            self.planned_courses.clear()
            
            # Add high priority courses for current term
            current_term = f"{self.term.currentText()} {self.term_year.value()}"
            for course in course_plan:
                course_name = course.get('Course', '').strip()
                course_term = course.get('Term', '').strip()
                priority = course.get('Priority', '').strip()
                
                if course_name and course_term == current_term and priority == 'High':
                    QListWidgetItem(course_name, self.planned_courses)
            
            return True
            
        except Exception as e:
            print(f"CSV parsing error: {e}")
            return False

    # ==================== DATA MANAGEMENT ====================

    def load_university_data(self):
        """Load university data from file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Load University Data", "", "JSON Files (*.json)"
        )
        
        if file_path:
            try:
                self.uni_data = self.data_manager.load_universities(Path(file_path))
                
                # Update UI
                self.current_uni.clear()
                self.target_uni.clear()
                
                uni_names = self.data_manager.get_university_names(self.uni_data)
                self.current_uni.addItems(uni_names)
                self.target_uni.addItems(uni_names)
                
                self.update_majors_list()
                
                QMessageBox.information(self, "Success", "University data loaded successfully!")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load data: {str(e)}")

    def export_plan(self):
        """Export current plan to file"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"transfer_plan_{timestamp}.txt"
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(self.script_display.toPlainText())
                f.write("\n\nWEEKLY SCHEDULE:\n")
                
                for row in range(self.schedule_grid.rowCount()):
                    time_slot = self.schedule_grid.verticalHeaderItem(row).text()
                    row_data = []
                    
                    for col in range(self.schedule_grid.columnCount()):
                        item = self.schedule_grid.item(row, col)
                        row_data.append(item.text() if item else "")
                    
                    f.write(f"{time_slot}: {', '.join(row_data)}\n")
            
            self.statusBar().showMessage(f"Plan exported to {filename}")
            QMessageBox.information(self, "Export Successful", f"Plan saved as {filename}")
            
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export plan: {str(e)}")

    def show_gantt_chart(self):
        """Generate and show Gantt chart"""
        try:
            planned = [self.planned_courses.item(i).text() 
                      for i in range(self.planned_courses.count())]
            
            if not planned:
                QMessageBox.information(self, "No Data", 
                                      "Please add courses to generate a Gantt chart.")
                return
            
            # Generate sample timeline data
            start_date = datetime.now()
            gantt_data = []
            
            for i, course in enumerate(planned):
                course_start = start_date + timedelta(weeks=i * 16)
                course_end = course_start + timedelta(weeks=16)
                
                gantt_data.append({
                    'Task': course,
                    'Start': course_start,
                    'Finish': course_end,
                    'Institution': 'Current School'
                })
            
            # Add transfer point
            transfer_date = course_end + timedelta(weeks=4)
            gantt_data.append({
                'Task': 'TRANSFER',
                'Start': transfer_date,
                'Finish': transfer_date + timedelta(days=7),
                'Institution': 'Transfer'
            })
            
            # Create Gantt chart
            df = pd.DataFrame(gantt_data)
            fig = px.timeline(
                df, 
                x_start="Start", 
                x_end="Finish", 
                y="Task",
                color="Institution",
                title="Transfer Course Timeline"
            )
            
            fig.update_layout(
                height=600,
                xaxis_title="Timeline",
                yaxis_title="Courses",
                showlegend=True
            )
            
            # Show in browser
            fig.show()
            
        except Exception as e:
            QMessageBox.critical(self, "Chart Error", f"Failed to generate Gantt chart: {str(e)}")

    def commit_to_journey(self):
        """Commit to the transfer journey and save plan"""
        try:
            commitment_data = {
                "commitment_date": datetime.now().isoformat(),
                "current_university": self.current_uni.currentText(),
                "target_university": self.target_uni.currentText(),
                "major": self.major.currentText(),
                "planned_courses": [
                    self.planned_courses.item(i).text() 
                    for i in range(self.planned_courses.count())
                ],
                "transfer_plan": self.script_display.toPlainText()
            }
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"committed_journey_{timestamp}.json"
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(commitment_data, f, indent=2)
            
            QMessageBox.information(
                self, 
                "Journey Started! 🎯", 
                f"Your transfer journey has been committed!\n\n"
                f"Plan saved as: {filename}\n\n"
                f"Stay focused and track your progress toward transferring to {self.target_uni.currentText()}!"
            )
            
        except Exception as e:
            QMessageBox.critical(self, "Commitment Error", f"Failed to save commitment: {str(e)}")

# ==================== APPLICATION ENTRY POINT ====================

def main():
    """Main application entry point"""
    load_env_from_script_dir()
    
    app = QApplication(sys.argv)
    app.setApplicationName("Transfer Assist")
    app.setApplicationVersion("1.0")
    
    window = TransferPlannerApp()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()