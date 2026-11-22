# AI Quiz Generator

A college CSE mini project. Students register, generate multiple-choice quizzes with Google Gemini from a topic or an uploaded PDF, take them with a timer, and review their results and history.

**Stack:** Flask, MySQL, Google Gemini API, PyMuPDF, Chart.js, HTML/CSS/JavaScript.

---

## 1. What you need installed

| Tool | Version | Check with |
|------|---------|------------|
| Python | 3.10 or newer | `python --version` |
| MySQL Server | 8.0 or newer | `mysql --version` |
| VS Code | any | |

Make sure the MySQL server is running and you know the root password.

## 2. Set up the project in VS Code

1. Open the `AI_Quiz_Generator` folder in VS Code (File > Open Folder).
2. Open a terminal (Terminal > New Terminal) and create a virtual environment:

   ```bash
   python -m venv venv
   ```

3. Activate it:
   - Windows (PowerShell): `venv\Scripts\Activate.ps1`
   - Windows (cmd): `venv\Scripts\activate.bat`
   - macOS / Linux: `source venv/bin/activate`

   If PowerShell blocks the script, run `Set-ExecutionPolicy -Scope Process Bypass` first.

4. Install the packages:

   ```bash
   pip install -r requirements.txt
   ```

5. In VS Code, press `Ctrl+Shift+P`, choose "Python: Select Interpreter" and pick the one inside `venv`.

## 3. Create the database

From the project folder run:

```bash
mysql -u root -p < schema.sql
# Get-Content -Raw .\schema.sql | & "C:\Program Files\MySQL\MySQL Server 8.0(a)\bin\mysql.exe" -u root -p
```

Enter your MySQL password when asked. This creates the `ai_quiz_generator` database and its five tables: `users`, `quizzes`, `questions`, `quiz_attempts`, `user_answers`.

(Alternative: open `schema.sql` in MySQL Workbench and run it.)

## 4. Get a Gemini API key

1. Go to <https://aistudio.google.com/apikey> and sign in with a Google account.
2. Click **Create API key** and copy the key.
3. Keep it private. Do not paste it into HTML or JavaScript files and do not upload it to GitHub.

## 5. Configure the `.env` file

1. Copy `.env.example` to a new file named `.env` (same folder).
2. Fill in the values:

   ```env
   SECRET_KEY=any-long-random-string
   DB_HOST=localhost
   DB_PORT=3306
   DB_USER=root
   DB_PASSWORD=your_mysql_password
   DB_NAME=ai_quiz_generator
   GEMINI_API_KEY=paste_your_key_here
   GEMINI_MODEL=gemini-2.5-flash
   MAX_UPLOAD_MB=10
   ```

   To make a good `SECRET_KEY`: `python -c "import secrets; print(secrets.token_hex(32))"`

   If you later see "model not found", open Google AI Studio, check the current model names and update `GEMINI_MODEL`.

## 6. Run the app

```bash
python app.py
```

Open <http://127.0.0.1:5000> in your browser. Stop the server with `Ctrl+C`.

## 7. How to use it

1. **Register** a student account, then **log in**.
2. **Generate Quiz:** enter subject, topic, number of questions (5, 10, 15) and difficulty.
3. **Upload PDF:** upload study notes with selectable text (up to 10 MB). Questions come only from the PDF.
4. **Take the quiz:** one question at a time, Previous/Next, question palette, mark for review, countdown timer (1 minute per question), and Submit. It auto-submits when time runs out.
5. **Result page:** score, percentage, time taken and a full answer review with explanations.
6. **My Quizzes / Quiz History / Dashboard:** retake quizzes, review old attempts and track your score trend and subject averages.

## 8. Project structure

```
AI_Quiz_Generator/
├── app.py              Flask app factory, CSRF check, error handlers
├── config.py           Settings loaded from .env
├── database.py         MySQL connection and all queries
├── schema.sql          Database creation script
├── requirements.txt
├── .env.example
├── services/
│   ├── gemini_service.py   Prompt, API call, response validation
│   └── pdf_service.py      PDF validation and text extraction
├── routes/
│   ├── auth.py         Register, login, logout, login_required
│   ├── dashboard.py    Stats and charts
│   ├── quiz.py         Generate, upload, take, submit, result
│   └── history.py      My Quizzes and Quiz History
├── templates/          9 HTML pages (Jinja)
├── static/             style.css, script.js
└── uploads/            Reserved (PDFs are processed in memory)
```

## 9. Security features

- Passwords hashed with Werkzeug; session-based login; protected routes.
- Parameterized SQL everywhere (no string-built queries).
- API key lives only in `.env` on the server.
- CSRF token on every POST form.
- Students can only open their own quizzes and results.
- Correct answers and explanations are never sent to the browser before submission; scoring happens on the server.
- Single-use submit token prevents duplicate submissions.
- Uploads are checked for extension, size and real PDF signature.

## 10. Troubleshooting

| Problem | Fix |
|---------|-----|
| "Could not reach the database" | Start MySQL, check `DB_*` values in `.env`, and confirm you ran `schema.sql`. |
| `Access denied for user` | Wrong `DB_PASSWORD`. |
| "The Gemini API key is not configured / rejected" | Set `GEMINI_API_KEY` in `.env` and restart the app. |
| "busy or quota used up" | Free-tier limit reached. Wait a minute and retry. |
| "Model not found" | Update `GEMINI_MODEL` in `.env`. |
| "No readable text was found in this PDF" | The PDF is scanned images. Use a PDF with selectable text. |
| `ModuleNotFoundError` | Activate the virtual environment and run `pip install -r requirements.txt`. |
| Changes to `.env` ignored | Restart `python app.py`. |

## 11. Manual test checklist

- [ ] Register, log in, log out; visiting `/dashboard` while logged out redirects to login
- [ ] Generate a 5-question Easy quiz on any topic
- [ ] Generate a 15-question Hard quiz and confirm 15 questions appear
- [ ] Upload a text PDF and generate a quiz; upload a scanned/empty PDF and see the error
- [ ] Try uploading a `.txt` file renamed to `.pdf` and see the error
- [ ] Answer some questions, mark one for review, jump using the palette, then submit
- [ ] Let the timer run out on a short quiz and confirm auto-submit
- [ ] Check the result counts and the answer review colors
- [ ] Refresh or press Back after submitting; no duplicate attempt is created
- [ ] Check Dashboard stats and charts, My Quizzes, Quiz History, Retake
- [ ] Register a second account and confirm it cannot see the first account's data
- [ ] Resize the browser to phone width and open the sidebar menu
