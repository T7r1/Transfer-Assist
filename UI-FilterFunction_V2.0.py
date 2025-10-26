class PlannerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.api_key = None
        self.worker = None
        self.history = []
        self.uni_data = read_universities(Path(__file__).resolve().parent / "university.json")
        self.course_catalog = {}  # Add this line
        self.load_course_catalog()  # Add this line
        self.init_ui()
        
    def load_course_catalog(self):
        """Initialize course catalog structure"""
        self.course_catalog = {
            'current_school': [],
            'target_school': []
        }
        
    def get_course_catalog_context(self):
        """Build course catalog data for AI context"""
        current_uni = self.current_uni.currentText().strip()
        target_uni = self.target_uni.currentText().strip()
        major = self.major.currentText().strip()
        
        # Get planned courses
        planned_courses = [self.planned.item(i).text() for i in range(self.planned.count())]
        
        # Get available courses
        available_courses = [self.available.item(i).text() for i in range(self.available.count())]
        
        catalog_context = {
            "current_university": current_uni,
            "target_university": target_uni, 
            "major": major,
            "planned_courses": planned_courses,
            "available_courses": available_courses,
            "current_term": f"{self.term.currentText()} {self.term_year.value()}",
            "today_date": datetime.now().strftime("%Y-%m-%d")
        }
        
        return catalog_context

    def suggest_missing_courses(self):
        """AI suggests courses based on major and transfer goals"""
        if not self.ensure_api_key():
            return
            
        catalog_context = self.get_course_catalog_context()
        
        prompt = f"""
        I am from {catalog_context['current_university']} majoring in {catalog_context['major']} 
        hoping to transfer to {catalog_context['target_university']}. Today is {catalog_context['today_date']}.
        
        My currently planned courses for {catalog_context['current_term']} are: {', '.join(catalog_context['planned_courses'])}
        Available courses I can choose from: {', '.join(catalog_context['available_courses'])}
        
        Please suggest additional courses from my available courses that would strengthen my transfer application 
        for my major. Focus on prerequisite courses and courses that demonstrate preparation for the target university's program.
        
        Return your response in two parts:
        1. Text suggestions explaining why these courses are recommended
        2. A CSV list of suggested courses to add to my plan
        
        Format your response exactly like this:
        
        text suggestion: {{"Your detailed explanation here"}}
        
        code: {{
        Course,Priority,Reason
        Course Name,High/Middle/Low,Brief reason
        }}
        """
        
        self.user_prompt.setPlainText(prompt)
        self.send_to_ai()

    def generate_transfer_plan(self):
        """Generate comprehensive transfer plan with Gantt chart timeline"""
        if not self.ensure_api_key():
            return
            
        catalog_context = self.get_course_catalog_context()
        
        prompt = f"""
        I am from {catalog_context['current_university']} majoring in {catalog_context['major']} 
        hoping to transfer to {catalog_context['target_university']}. Today is {catalog_context['today_date']}.
        
        My current courses: {', '.join(catalog_context['planned_courses'])}
        
        Develop a comprehensive transfer plan for me including:
        1. Required courses for admission to {catalog_context['target_university']} for {catalog_context['major']}
        2. Recommended timeline spanning multiple terms until transfer
        3. Prerequisite sequencing
        
        Return your response in two parts:
        
        text suggestion: {{"Your comprehensive advice including course sequencing, deadlines, and transfer requirements"}}
        
        code: {{
        Course,Term,Priority,DurationWeeks,Department,Credits
        Course Name,Fall 2024,High,16,Department,4
        }}
        
        For the CSV, use these term formats: Fall 2024, Spring 2025, Summer 2025, etc.
        DurationWeeks: 16 for full semester, 8 for summer
        Priority: High (required for transfer), Medium (recommended), Low (optional)
        """
        
        self.user_prompt.setPlainText(prompt)
        self.send_to_ai()