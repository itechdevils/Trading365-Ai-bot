# Trading 365 FB Manager v0.3 — AI Agent Test Source

Developed by Mazhar Rafiq • Powered by Trading 365 Software Solutions

## Build on GitHub (Windows)
1. Create a **new** GitHub repository; upload all files including `.github/workflows/build-windows.yml`.
2. Actions > Build Trading 365 FB Manager Windows > Run workflow.
3. Download artifact `Trading365-FB-Manager-Windows`, extract and run the EXE.
4. Google Chrome must be installed. Selenium Manager needs internet to obtain a compatible driver on first use. Ollama is optional.

## Accounts and secure sign-in
- Accounts / Profiles > Add Profile creates a label.
- Import Accounts CSV accepts `name,username,password` (or `label,email,password`). CSV passwords are read into volatile application memory only and never saved to data.json. **Your original CSV remains unencrypted on disk: delete it securely after import if appropriate.**
- Select account > Secure Login > enter credentials > Start Login. This opens Chrome with its dedicated user data directory, fills the Facebook sign-in form and submits. Complete CAPTCHA, 2FA or checkpoints yourself. Successful sign-in is NOT automatically verified; check the browser.
- Do not open a second Chrome instance with the same profile while Secure Login is active. Stop Browser closes a Selenium-managed browser, if any.
- Manual sign-in via Open / Focus remains available. Passwords are not sent to Ollama. Avoid typing secrets into AI chat.
- `Login Imported` explains the one-at-a-time confirmation workflow; it does not batch submit passwords.

## AI Agent
- AI tab > Agent mode `Manual`: approval dialog for supported actions.
- `Autonomous`: supported, low-risk local actions can run without confirmation.
- Commands supported without Ollama: `create 10 profiles`, `open phone 3`, `account status report`, `open groups/123456789`.
- Other prompts use optional Ollama read-only assistant (`ollama pull llama3.2`, run Ollama).
- No arbitrary AI-generated code or OS commands are executed. No unattended Facebook join/post or security-bypass actions.

## Voice
- AI tab > Listen (Windows): uses Windows System.Speech dictation, listens up to 8 seconds, places recognized words in command field for your review. Click Execute / Ask Agent to act.
- Speak Last Reply uses Windows speech synthesis. Recognition depends on configured Windows speech language; Roman Urdu recognition is not guaranteed. Microphone required.

## Groups and scheduling
- Group Library > Add Group ID / Link supports numeric Facebook group IDs and HTTPS Facebook group links; CSV supports `name,keyword,url` or `group_id`.
- Find by Keyword opens Facebook group search in browser for manual review.
- Review Queue > choose account, keyword, group count, interval, optional Facebook post link. Join and post queues prepare tasks for user review; **do not automatically join or post**.
- Open Selected for Approval opens a group page. Complete permitted actions yourself, then Mark Done.

## Limits and testing
- Windows EXE has NOT been runtime tested here; this is a source/test release, not a verified production installer.
- No embedded live Chrome previews, auto group discovery/scraping, automatic join/post, guaranteed login verification, wake-word detection, or self-updating/self-modifying agent.
- Browser login page layout and Selenium/Chrome version changes can require maintenance.
- Local app data is stored in `%LOCALAPPDATA%\Trading365\FBManagerV02` for compatibility with v0.2. Back it up before upgrading.
