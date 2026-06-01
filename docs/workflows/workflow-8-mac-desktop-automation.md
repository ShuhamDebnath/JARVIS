
# Workflow 8 — Mac Desktop Automation

> Phase 6 | Department: Automation | On demand | Human gate: confirm risky actions

## What This Workflow Does

You say or type a command in plain English. Jarvis executes it on your Mac. For safe commands (open app, create folder, search files) it executes immediately. For risky commands (delete, move large batches, system changes) it shows you the command and asks for confirmation first.

**Input:** Natural language command via voice or text  
**Output:** Command executed on Mac + result reported back  
**Examples:**
- `"Open Xcode and create a new Flutter project called HabitApp"`
- `"Find all files larger than 100MB in my Downloads folder and list them"`
- `"Create a folder called 'jarvis-output' on the Desktop"`
- `"Search my Desktop for any PNG files and move them to Screenshots folder"`

## Agent Hierarchy

```
Jarvis CEO
└── automation_dept_crew
        manager_agent: automation_director
    └── Mac Automation Agent  (Open Interpreter)
```

## Safety Classification

Before any command runs, the CEO classifies it:

| Risk level | Examples | Behaviour |
|------------|---------|-----------|
| SAFE | Open app, create folder, list files, search | Execute immediately |
| CAUTION | Move files, rename in bulk, install software | Show command, ask confirm |
| RISKY | Delete files, system changes, empty Trash | Show command, explain consequence, require explicit "yes" |

The CEO's Python classification logic (not an LLM call — a simple keyword matcher) checks for: `rm`, `delete`, `remove`, `format`, `sudo`, `uninstall` → RISKY. `mv`, `move`, `rename`, `install` → CAUTION. Everything else → SAFE.

## Pipeline

1. User gives command via voice or text
2. CEO classifies risk level using keyword matcher (Python, no LLM)
3. If SAFE → Mac Automation Agent executes immediately
4. If CAUTION or RISKY → CEO shows the shell command it will run and asks confirmation
5. User confirms → Mac Automation Agent executes
6. User declines → workflow ends with no action
7. Result reported back to user in plain English

## agents.yaml additions

```yaml
mac_automation_agent:
  dept: automation_dept
  role: Mac Desktop Automation Agent
  goal: >
    Execute this Mac command: {command}
    Use Open Interpreter to translate the natural language command into a shell
    command and run it. Report the result in plain English — not raw terminal output.
    If the command fails, explain what went wrong and what the user should try instead.
  backstory: >
    You are a Mac power user who knows every terminal shortcut.
    You execute commands safely and report results clearly.
    You never run a risky command without explicit confirmation.
    You always translate raw terminal output into plain English for the developer.
  llm: deepseek/deepseek-chat
  tools: [OpenInterpreterTool]
  allow_delegation: false
  memory: false

automation_director:
  dept: automation_dept
  role: Automation Department Director
  goal: >
    Coordinate automation tasks. Activate the correct automation agent for the task.
    For Mac commands: activate Mac Automation Agent.
    For social posting: activate Social Poster.
    For upload watching: activate Upload Watcher.
  backstory: >
    You are the execution layer director. You route tasks to the right automation tool
    and ensure nothing runs without appropriate confirmation.
  llm: deepseek/deepseek-chat
  allow_delegation: true
  memory: false
```

## tasks.yaml additions

```yaml
mac_automation_task:
  description: >
    Execute this Mac command: {command}
    Risk level has been pre-classified as: {risk_level}
    If SAFE: execute immediately and report result.
    If CAUTION or RISKY: this task will only run after human confirmation
    (the CEO orchestrator handles the confirmation gate before calling kickoff).
    Translate the natural language command into the correct shell command.
    Report result in plain English — not raw terminal output.
    If command fails: explain what went wrong and suggest what to try instead.
  expected_output: >
    Plain English result of the command — success confirmation or failure explanation.
  agent: mac_automation_agent
```

## Files Involved
```
backend/tools/open_interpreter_tool.py   # wraps Open Interpreter
backend/crews/jarvis_ceo.py              # add run_workflow_8(command, run_id)
backend/main.py                          # add POST /workflow/automate
```

## Cost Estimate
~₹1–3 per command. Very low — single agent, short context.

---