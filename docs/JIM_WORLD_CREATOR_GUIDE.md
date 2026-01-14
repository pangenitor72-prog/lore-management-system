# Mantle World Creator Guide

## Welcome, Worldsmith!

You have access to create and import worlds that players can explore. This guide covers everything you need to know.

---

## Getting Started

### Accessing the App

1. Go to: **https://lore-management-system.fly.dev/**
2. Enter your invite code: **JIM-ADMIN** (or your assigned code)
3. You'll see the main landing page with the raven mascot

### Admin Access (Required for World Creator)

The World Creator is an admin-only feature. To access it:
1. Press **Ctrl + Shift + A** (secret admin shortcut)
2. Enter the password: **worldsmith**
3. Scroll down to the **"🌍 World Creator"** section
4. Click **"📁 Open Full World Creator (File Explorer)"**

---

## The World Creator

From the Admin panel, click **"Open Full World Creator"** to access the world creation flow.

### Two Ways to Create Worlds

#### Option 1: Choose a Curated World
Browse the pre-made worlds organized by genre:
- Fantasy, Horror, Sci-Fi, Mystery, Romance
- Click any world card to select it
- Or choose "Fresh Canvas" to start from nothing

#### Option 2: Import Your Own Lore
Use the **File Explorer** to import your own world-building notes.

---

## The File Explorer (New!)

The File Explorer lets you import your lore files easily.

### How to Use It

1. **Navigate to:** World Creator → "Import Your Own" section
2. **Add files using any method:**
   - **Drag & Drop:** Drag files or entire folders onto the drop zone
   - **Browse Files:** Click "+ Add Files" to pick individual files
   - **Browse Folder:** Click "+ Add Folder" to select a whole folder

3. **Manage your files:**
   - Files appear in a list with checkboxes
   - **Toggle checkboxes** to include/exclude specific files
   - **Click "Preview"** to see a file's contents before importing
   - **Click X** to remove a file from the list
   - Use "Select All" / "Deselect All" for bulk selection

4. **Start the import:**
   - Click **"Preview Extraction"**
   - AI will analyze and extract entities from your lore

### Supported File Types
- `.txt` - Plain text files
- `.md` - Markdown files
- `.json` - JSON files (will extract `lore_content` if present)
- `.pdf` - PDF documents

### Tips for File Organization
- Group related lore into separate files (characters.txt, locations.txt, etc.)
- Use descriptive filenames - they'll appear in the file list
- You can add multiple batches - files won't duplicate

---

## The Entity Review Panel (Human-in-the-Loop)

After clicking "Preview Extraction", the AI analyzes your lore and shows what it found.

### What You'll See
- **Entity cards** for each character, location, faction, item, or concept found
- Each card has a checkbox (checked = will be imported)
- Entity type and description shown on each card

### How to Review

1. **Select/Deselect entities:**
   - Click individual checkboxes
   - Use "Select All" / "Deselect All" buttons
   - Filter by type (Characters, Locations, etc.)

2. **Edit entities:**
   - Click on a name to edit it inline
   - Fix AI mistakes before importing

3. **Watch for warnings:**
   - Cards with orange borders indicate possible duplicates
   - Review these carefully - the AI flags similar names

4. **Complete the import:**
   - Click **"Import Selected Entities"**
   - Only checked entities are saved to the database

---

## Creating Curated Worlds (Admin)

With admin access, you can create curated worlds that appear in the world browser.

### The Fields

| Field | What to Enter |
|-------|---------------|
| **World Name** | Display name players see (e.g., "The Shattered Isles") |
| **World ID** | Auto-generated from name, or customize it |
| **Short Description** | 1-2 enticing sentences for the browse view |
| **Genre(s)** | Select which genres fit (can pick multiple) |
| **Tone(s)** | The mood of your world |
| **The Lore** | The big text box - this is where your world lives |

---

## Writing Great Lore

The lore content is what the AI uses to bring your world to life.

### Characters
Give them personality, not just descriptions:
> *"Lady Moira is cunning but kind - she'll test you before she trusts you. She lost someone years ago and still carries that wound. Her sharp wit hides a generous heart."*

### Locations
Make them feel real:
> *"The Obsidian Tower stands on the edge of the Whispering Cliffs. Inside, the walls are lined with books in languages that haven't been spoken for centuries. It always smells faintly of old paper and secrets."*

### Relationships & Tensions
What makes the world interesting?
> *"House Varell and House Dren have been feuding for three generations. No one remembers why it started, but everyone remembers what they've lost."*

### Secrets & Plot Hooks
Give the AI ammunition to create intrigue:
> *"Someone has been sending anonymous letters to the heirs of both houses. The letters contain information that no one should know."*

---

## Tips for Success

1. **Write like you're telling a friend about a favorite place** - not like an encyclopedia
2. **Characters need flaws and desires** - perfect people are boring
3. **Leave mysteries unsolved** - the AI will work with players to explore them
4. **Mix genres if it fits** - a romance can have mystery, adventure can have horror
5. **Use the file explorer** for large amounts of content - easier than pasting

---

## Example World

**Name:** The Last Library
**Description:** A forgotten library at the edge of reality, where lost books find their way home.
**Genres:** Fantasy, Mystery
**Tones:** Mysterious, Intimate, Hopeful

**Lore:**
> The Last Library exists in the space between worlds. It has no location - you find it when you need it, and only if you need it badly enough.
>
> The Librarian is old - impossibly old - with kind eyes and ink-stained fingers. They never give their name. They speak in riddles but always mean well. They know every book that has ever been lost, and they know which one you're looking for before you do.
>
> The stacks go on forever. The deeper you go, the older the books become. Some of the books down there aren't written in any human language. Some of them whisper when you walk past. The Librarian warns against going past the Seventh Reading Room - not because it's forbidden, but because those who do rarely come back the same.

---

## The Knowledge Graph

After importing entities, you can visualize them:
1. Click **"View Lore Graph"** from the ingest screen
2. Or navigate to the Graph screen from the main menu
3. See all entities and their relationships as a visual network
4. Click any node to inspect its details

---

## Quick Reference

| Action | How |
|--------|-----|
| Access app | https://lore-management-system.fly.dev/ |
| Admin mode | Ctrl + Shift + A, password: worldsmith |
| World Creator | Admin → 🌍 World Creator → Open Full World Creator |
| Import files | World Creator → Import Your Own → File Explorer |
| Review entities | After Preview Extraction, check/uncheck cards |
| View graph | Click "View Lore Graph" after import |
| Browse worlds | World Creator → Curated Worlds section |

---

## Questions?

Just ask! This is a creative collaboration. If you have an idea that doesn't fit the form, we can make it work.

Happy worldbuilding!
