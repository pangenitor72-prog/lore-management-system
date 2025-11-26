# LMS CONVERSATIONAL INTERFACE - FINAL SPECIFICATION
**Gemini-Powered Lore Management System for Jim's 30-Year D&D Campaign**

---

## EXECUTIVE SUMMARY

You (Gemini) will:
1. **Build** the conversational UI for this lore management system
2. **Power** the conversational agent that helps Jim manage his lore
3. **Eventually** serve as the AIRPG DM that uses this lore database

This is a conversational-first interface with context-aware visual components. Jim talks to you naturally, you call backend APIs and present results in appropriate visual formats.

---

## ARCHITECTURE OVERVIEW

```
┌─────────────────────────────────────────────┐
│  GEMINI (Multi-Role Agent)                  │
├─────────────────────────────────────────────┤
│                                             │
│  Role 1: BUILDER (Current Phase)            │
│  └─ Creates frontend UI                     │
│  └─ Implements conversational interface     │
│  └─ Integrates with backend                 │
│                                             │
│  Role 2: LMS AGENT (Operational)            │
│  └─ Parses Jim's natural language           │
│  └─ Calls backend APIs via function calling │
│  └─ Updates UI contexts dynamically         │
│  └─ Maintains conversation state            │
│                                             │
│  Role 3: AIRPG DM (Future)                  │
│  └─ Queries finalized lore database         │
│  └─ Generates narrative                     │
│  └─ Runs game sessions                      │
│                                             │
└─────────────────────────────────────────────┘
         ↓                    ↑
         ↓                    ↑
    [Frontend UI]      [Backend API]
    (React/HTML)       (FastAPI - Port 8000)
```

---

## PART 1: CORE SYSTEM DESIGN

### System Prompt (Your Operational Role)

```
You are the Lore Management Assistant for Jim's 30-year D&D campaign.

CAPABILITIES:
- Parse natural language requests about lore management
- Call backend APIs to execute tasks
- Present results in appropriate visual formats
- Guide Jim through complex workflows
- Remember conversation context
- Provide helpful suggestions

PERSONALITY:
- Wise librarian managing ancient archives
- Patient and thorough
- Enthusiastic about lore organization
- Speaks with fantasy RPG flavor when appropriate
- Friendly and encouraging

RULES (CRITICAL):
- Always confirm destructive actions
- Present contradictions but NEVER resolve them without human approval (Gospel Principle)
- Offer helpful suggestions after completing tasks
- Maintain conversation context
- Show impact of decisions before execution
- Provide undo option for all actions

UI CONTEXTS YOU CAN SUMMON:
- upload: File ingestion interface
- search: Entity search results with filters
- contradiction: Contradiction review cards
- entity_detail: Full entity information
- canon_decision: Version comparison for canon choice
- dashboard: System status and progress overview
```

---

## PART 2: FRONTEND COMPONENTS TO BUILD

### 1. Persistent Elements (Always Visible)

**Chat Interface (Bottom 30% or Side Panel)**
```javascript
<ChatInterface>
  <MessageHistory>
    {messages.map(msg => (
      msg.sender === 'gemini' 
        ? <GeminiMessage avatar="sage-icon">{msg.text}</GeminiMessage>
        : <UserMessage avatar="dm-icon">{msg.text}</UserMessage>
    ))}
  </MessageHistory>
  
  <InputArea>
    <TextInput 
      placeholder="Ask me anything about your lore..." 
      onSubmit={sendToGemini}
    />
    <SendButton />
  </InputArea>
</ChatInterface>
```

**Quick Actions Bar (Top or Persistent)**
```javascript
<QuickActionsBar>
  <UndoButton 
    disabled={!canUndo} 
    onClick={undo}
    tooltip="Undo last action (Ctrl+Z)"
  />
  
  {/* Context-specific actions */}
  {context === 'search' && (
    <NewEntityButton onClick={createNew} />
  )}
  {context === 'contradiction' && (
    <SkipButton onClick={skipToNext} />
  )}
</QuickActionsBar>
```

**Context Indicator (Top Bar)**
```javascript
<ContextIndicator>
  <Breadcrumb>
    {contextPath.map(crumb => (
      <Crumb onClick={() => navigateTo(crumb)}>{crumb.label}</Crumb>
    ))}
  </Breadcrumb>
  <BackButton visible={canGoBack} />
</ContextIndicator>
```

**Status Corner**
```javascript
<StatusCorner>
  <ConnectionStatus status={wsStatus} />
  <QueueCount count={processingCount} />
  <ContradictionAlert count={unresolvedCount} />
</StatusCorner>
```

---

### 2. Dynamic Canvas (Context-Dependent)

```javascript
<DynamicCanvas>
  {context === 'upload' && <UploadContext data={contextData} />}
  {context === 'search' && <SearchContext data={contextData} />}
  {context === 'contradiction' && <ContradictionContext data={contextData} />}
  {context === 'entity_detail' && <EntityDetailContext data={contextData} />}
  {context === 'canon_decision' && <CanonDecisionContext data={contextData} />}
  {context === 'dashboard' && <DashboardContext data={contextData} />}
  {context === null && <WelcomeScreen />}
</DynamicCanvas>
```

---

### 3. Context Components (Detailed Specs)

#### **UPLOAD CONTEXT**
```javascript
<UploadContext>
  <DropZone 
    onDrop={handleFiles}
    onBrowse={openFilePicker}
  >
    <Icon>📜</Icon>
    <Text>Drop text files here or click to browse</Text>
  </DropZone>
  
  <ProcessingQueue visible={files.length > 0}>
    {files.map(file => (
      <QueueItem>
        <FileName>{file.name}</FileName>
        <Status status={file.status}>
          {file.status === 'processing' && <Spinner />}
          {file.status === 'complete' && '✓'}
          {file.status === 'error' && '✗'}
        </Status>
      </QueueItem>
    ))}
  </ProcessingQueue>
  
  <ResultsSummary visible={batchComplete}>
    <Stat>
      <Number>{stats.filesProcessed}</Number>
      <Label>Files Processed</Label>
    </Stat>
    <Stat>
      <Number>{stats.entitiesFound}</Number>
      <Label>Entities Found</Label>
      <Action onClick={() => switchContext('search')}>View All</Action>
    </Stat>
    <Stat warning={stats.contradictions > 0}>
      <Number>{stats.contradictions}</Number>
      <Label>Contradictions Detected</Label>
      <Action onClick={() => switchContext('contradiction')}>Review</Action>
    </Stat>
  </ResultsSummary>
</UploadContext>
```

#### **SEARCH CONTEXT**
```javascript
<SearchContext>
  <FilterBar>
    <FilterGroup label="Confidence">
      <Select options={['ANY', 'HIGH', 'CONFIRMED']} />
    </FilterGroup>
    <FilterGroup label="Type">
      <Checkboxes options={['Character', 'Location', 'Item', 'Event']} />
    </FilterGroup>
    <FilterGroup label="Party Knowledge">
      <Select options={['ANY', 'KNOWN', 'UNKNOWN', 'RUMOR']} />
    </FilterGroup>
    <ClearFilters />
  </FilterBar>
  
  <ResultsHeader>
    <Count>Found {results.length} entities</Count>
    <SelectAll visible={results.length > 0} />
  </ResultsHeader>
  
  <ResultsGrid>
    {results.map(entity => (
      <EntityCard 
        onClick={() => viewEntity(entity.canon_id)}
        onHover={showTooltip}
      >
        <Checkbox visible={bulkMode} />
        <Name>{entity.canonical_name}</Name>
        <Type>{entity.type}</Type>
        <Badges>
          <ConfidenceBadge level={entity.confidence} />
          <KnowledgeBadge level={entity.party_knowledge} />
        </Badges>
      </EntityCard>
    ))}
  </ResultsGrid>
  
  <BulkActionBar visible={selectedCount > 0}>
    <SelectedCount>{selectedCount} selected</SelectedCount>
    <BulkEdit onClick={openBulkEditor} />
    <BulkExport onClick={exportSelected} />
  </BulkActionBar>
</SearchContext>
```

#### **CONTRADICTION CONTEXT**
```javascript
<ContradictionContext>
  <ContradictionCard>
    <Header>
      <Type>{data.contradiction_type}</Type>
      <SeverityBadge level={data.severity} />
    </Header>
    
    <Description>{data.description}</Description>
    
    <VersionComparison>
      <Version label="Version A">
        <Text>{data.versions[0].text}</Text>
        <Metadata>
          <Source>{data.versions[0].source}</Source>
          <Confidence>{data.versions[0].confidence}</Confidence>
        </Metadata>
      </Version>
      
      <Version label="Version B">
        <Text>{data.versions[1].text}</Text>
        <Metadata>
          <Source>{data.versions[1].source}</Source>
          <Confidence>{data.versions[1].confidence}</Confidence>
        </Metadata>
      </Version>
    </VersionComparison>
    
    <ImpactPreview collapsed={!showingImpact}>
      <Toggle onClick={toggleImpact}>
        Show Impact ({affectedCount} entities affected)
      </Toggle>
      <AffectedList visible={showingImpact}>
        {affectedEntities.map(entity => (
          <AffectedEntity>
            <Name>{entity.name}</Name>
            <Change>
              <Before>{entity.before}</Before>
              →
              <After>{entity.after}</After>
            </Change>
          </AffectedEntity>
        ))}
      </AffectedList>
    </ImpactPreview>
    
    <Actions>
      <PrimaryButton onClick={() => resolve('version_a')}>
        Make A Canon
      </PrimaryButton>
      <PrimaryButton onClick={() => resolve('version_b')}>
        Make B Canon
      </PrimaryButton>
      <SecondaryButton onClick={skip}>
        Need More Info
      </SecondaryButton>
      <SecondaryButton onClick={dismiss}>
        Dismiss
      </SecondaryButton>
    </Actions>
  </ContradictionCard>
  
  <NavigationHint>
    {remainingCount} more contradictions after this
  </NavigationHint>
</ContradictionContext>
```

#### **ENTITY DETAIL CONTEXT**
```javascript
<EntityDetailContext>
  <BackButton onClick={returnToSearch} />
  
  <EntityHeader>
    <Name>{entity.canonical_name}</Name>
    <Meta>
      <Type>{entity.type}</Type>
      <ConfidenceBadge level={entity.confidence} />
      <KnowledgeBadge level={entity.party_knowledge} />
    </Meta>
  </EntityHeader>
  
  <Section title="Aliases">
    {entity.aliases.map(alias => <Tag>{alias}</Tag>)}
  </Section>
  
  <Section title="Description">
    <Text>{entity.description}</Text>
  </Section>
  
  <Section title="Related Entities">
    {entity.related.map(related => (
      <RelatedEntity 
        onClick={() => viewEntity(related.id)}
        onHover={showTooltip}
      >
        <Name>{related.name}</Name>
        <Relationship>{related.relationship}</Relationship>
      </RelatedEntity>
    ))}
  </Section>
  
  <Section title="Sources">
    {entity.sources.map(source => (
      <Source>
        <FileName>{source.file}</FileName>
        <Mentions>{source.mention_count} mentions</Mentions>
      </Source>
    ))}
  </Section>
  
  <Actions>
    <EditButton onClick={openEditor} />
    <SetKnowledgeButton onClick={setPartyKnowledge} />
    <ViewGraphButton onClick={() => showGraph(entity.canon_id)} />
  </Actions>
</EntityDetailContext>
```

#### **DASHBOARD CONTEXT**
```javascript
<DashboardContext>
  <WelcomeMessage>
    Welcome back, Jim. Here's your lore system status.
  </WelcomeMessage>
  
  <StatsGrid>
    <StatCard>
      <Number>{stats.totalEntities}</Number>
      <Label>Total Entities</Label>
    </StatCard>
    
    <StatCard>
      <Number>{stats.confirmedPercent}%</Number>
      <Label>Entities Confirmed</Label>
      <ProgressBar value={stats.confirmedPercent} />
    </StatCard>
    
    <StatCard>
      <Number>{stats.withDescriptions}%</Number>
      <Label>Have Descriptions</Label>
      <ProgressBar value={stats.withDescriptions} />
    </StatCard>
    
    <StatCard warning={stats.contradictions > 0}>
      <Number>{stats.contradictions}</Number>
      <Label>Contradictions Remaining</Label>
      <Action onClick={() => switchContext('contradiction')}>
        Review Now
      </Action>
    </StatCard>
  </StatsGrid>
  
  <RecentActivity>
    <SectionTitle>Recent Activity</SectionTitle>
    {activity.map(item => (
      <ActivityItem>
        <Icon>{item.icon}</Icon>
        <Text>{item.description}</Text>
        <Time>{item.timestamp}</Time>
      </ActivityItem>
    ))}
  </RecentActivity>
  
  <SuggestedActions>
    <SectionTitle>Suggested Next Steps</SectionTitle>
    {suggestions.map(suggestion => (
      <Suggestion onClick={suggestion.action}>
        {suggestion.text}
      </Suggestion>
    ))}
  </SuggestedActions>
</DashboardContext>
```

---

## PART 3: CRITICAL FEATURES (BUILD IMMEDIATELY)

### 1. UNDO SYSTEM (HIGHEST PRIORITY)

**Backend Endpoint:**
```
POST /api/undo
Response: {success: bool, restored_state: object}
```

**Frontend Implementation:**
```javascript
// Action history (keep last 10)
const actionHistory = [];

function recordAction(action, beforeState) {
  actionHistory.push({
    type: action.type,
    timestamp: Date.now(),
    before: beforeState,
    description: action.description
  });
  
  // Keep only last 10
  if (actionHistory.length > 10) {
    actionHistory.shift();
  }
}

function undo() {
  if (actionHistory.length === 0) return;
  
  const lastAction = actionHistory.pop();
  
  // Call backend to restore state
  fetch('/api/undo', {
    method: 'POST',
    body: JSON.stringify(lastAction)
  }).then(response => {
    // Refresh UI with restored state
    refreshCurrentContext();
  });
}

// Keyboard shortcut
document.addEventListener('keydown', (e) => {
  if (e.ctrlKey && e.key === 'z') {
    undo();
  }
});
```

**UI:**
- Undo button always visible in Quick Actions bar
- Shows tooltip with what will be undone
- Disabled state when nothing to undo
- Keyboard shortcut: Ctrl+Z

**Gemini Integration:**
- Understands "undo that", "go back", "reverse that"
- Narrates what was undone: "Undid resolution of Black King contradiction. Restored to previous state."

---

### 2. IMPACT PREVIEW (CRITICAL FOR GOSPEL PRINCIPLE)

**Backend Endpoint:**
```
POST /api/preview-canon-decision
Body: {contradiction_id, chosen_version}
Response: {
  affected_entities: [{id, name, field, old_value, new_value}],
  affected_count: number
}
```

**Frontend Implementation:**
```javascript
<ImpactPreview>
  <Toggle onClick={loadImpact}>
    Show Impact ({affectedCount} entities affected)
    {loading && <Spinner />}
  </Toggle>
  
  <AffectedList visible={expanded}>
    {affectedEntities.map(entity => (
      <AffectedEntity>
        <EntityName>{entity.name}</EntityName>
        <FieldChange>
          <Field>{entity.field}:</Field>
          <OldValue>{entity.old_value}</OldValue>
          <Arrow>→</Arrow>
          <NewValue>{entity.new_value}</NewValue>
        </FieldChange>
      </AffectedEntity>
    ))}
  </AffectedList>
  
  <ConfirmButton 
    disabled={!hasViewedImpact}
    onClick={proceedWithDecision}
  >
    I understand the impact, proceed
  </ConfirmButton>
</ImpactPreview>
```

**Requirements:**
- User MUST expand impact preview before confirming
- Confirm button only enabled after viewing
- Shows clear before/after for each change
- Highlights if changes cascade to many entities

---

### 3. INTERACTIVE SEARCH FILTERS

**Frontend Implementation:**
```javascript
<FilterBar>
  <FilterGroup label="Confidence">
    <RadioButtons
      options={[
        {value: 'ANY', label: 'Any Confidence'},
        {value: 'HIGH', label: 'High or Confirmed'},
        {value: 'CONFIRMED', label: 'Confirmed Only'}
      ]}
      value={filters.confidence}
      onChange={updateFilter}
    />
  </FilterGroup>
  
  <FilterGroup label="Type">
    <CheckboxGroup
      options={['Character', 'Location', 'Item', 'Event', 'Faction']}
      selected={filters.types}
      onChange={updateFilter}
    />
  </FilterGroup>
  
  <FilterGroup label="Party Knowledge">
    <Select
      options={['ANY', 'KNOWN', 'UNKNOWN', 'RUMOR', 'SECRET']}
      value={filters.knowledge}
      onChange={updateFilter}
    />
  </FilterGroup>
  
  <ClearFilters onClick={resetFilters}>
    Clear All
  </ClearFilters>
</FilterBar>
```

**Gemini Integration:**
- Can set filters via conversation: "Only show confirmed characters"
- Responds to filter changes: "Filtered to 23 confirmed characters"
- Suggests useful filters: "Want to filter by campaign era?"

---

### 4. QUICK ACTIONS BAR

**Context-Aware Actions:**
```javascript
function getQuickActions(context) {
  const actions = [
    {id: 'undo', label: 'Undo', icon: '↶', visible: 'always'}
  ];
  
  if (context === 'search') {
    actions.push(
      {id: 'new_entity', label: 'New', icon: '+'},
      {id: 'bulk_select', label: 'Select', icon: '☑'}
    );
  }
  
  if (context === 'contradiction') {
    actions.push(
      {id: 'skip', label: 'Skip', icon: '⏭'},
      {id: 'help', label: 'Help', icon: '?'}
    );
  }
  
  return actions;
}

<QuickActionsBar>
  {getQuickActions(currentContext).map(action => (
    <ActionButton
      key={action.id}
      onClick={() => handleAction(action.id)}
      disabled={!isActionAvailable(action.id)}
      tooltip={action.label}
    >
      {action.icon}
    </ActionButton>
  ))}
</QuickActionsBar>
```

---

## PART 4: BACKEND API FUNCTIONS

### Function Definitions for Gemini

```javascript
// Upload files
upload_files(files: File[]) 
  → {batch_id: string, status: string, files_queued: number}

// Search entities
search_entities(query: string, filters: FilterObject) 
  → {results: Entity[], total_count: number}

// Get entity details
get_entity(canon_id: string) 
  → Entity

// List contradictions
list_contradictions(filters?: FilterObject) 
  → Contradiction[]

// Get contradiction details
get_contradiction(contradiction_id: string) 
  → Contradiction

// Preview canon decision impact
preview_canon_decision(contradiction_id: string, chosen_version: string)
  → {affected_entities: AffectedEntity[], affected_count: number}

// Resolve contradiction (with confirmation)
resolve_contradiction(
  contradiction_id: string, 
  canonical_version: string,
  reason: string
) → {success: boolean, updated_entities: number}

// Make canon decision
make_canon_decision(
  entity_id: string, 
  approved_version: object,
  reason: string
) → {success: boolean, decision_id: string}

// Bulk update entities
bulk_update_entities(
  entity_ids: string[], 
  updates: object
) → {success_count: number, failed_count: number}

// Get system stats
get_system_status() 
  → {
    total_entities: number,
    confirmed_percent: number,
    with_descriptions: number,
    contradictions_pending: number,
    recent_uploads: Upload[]
  }

// Undo last action
undo() 
  → {success: boolean, restored_state: object}
```

---

## PART 5: GEMINI ↔ FRONTEND COMMUNICATION

### Message Protocol

**User Message → Gemini:**
```json
{
  "type": "user_message",
  "text": "Show me all contradictions about the Black King",
  "current_context": "search",
  "current_state": {...}
}
```

**Gemini Response → Frontend:**
```json
{
  "text": "I found 3 contradictions about the Black King. Here's the first one:",
  "context": "contradiction",
  "data": {
    "contradiction_id": "c123",
    "type": "Temporal Discrepancy",
    "severity": "HIGH",
    "versions": [...]
  },
  "actions": [
    {"id": "resolve_a", "label": "Make A Canon"},
    {"id": "resolve_b", "label": "Make B Canon"},
    {"id": "skip", "label": "Skip"}
  ]
}
```

**User Action → Gemini:**
```json
{
  "type": "action",
  "action_id": "resolve_a",
  "params": {
    "contradiction_id": "c123",
    "canonical_version": "version_a"
  }
}
```

---

## PART 6: FANTASY RPG AESTHETIC

### Visual Design System

**Color Palette:**
- Background: `#1a0f0a` (dark leather)
- Surface: `#2a1810` (aged wood)
- Parchment: `#f4e8d0` (cream with texture)
- Borders: `#8b7355` (bronze/gold)
- Text Primary: `#f4e8d0`
- Text Secondary: `#c9b896`
- Accent Success: `#d4af37` (gold)
- Accent Warning: `#ff8c00` (amber)
- Accent Error: `#8b0000` (deep red)

**Typography:**
```css
/* Headers */
font-family: 'Cinzel', serif;
font-weight: 300;
letter-spacing: 0.15em;
text-transform: uppercase;

/* Body */
font-family: 'Crimson Text', serif;
font-size: 16px;
line-height: 1.6;

/* Data/Stats */
font-family: 'Lato', sans-serif;
font-variant-numeric: tabular-nums;
```

**Component Styling:**

**Cards:**
```css
.card {
  background: linear-gradient(135deg, #2a1810 0%, #1a0f0a 100%);
  border: 2px solid #8b7355;
  box-shadow: 
    0 4px 8px rgba(0,0,0,0.4),
    inset 0 1px 0 rgba(255,255,255,0.1);
  padding: 1.5rem;
}
```

**Buttons:**
```css
.button-primary {
  background: linear-gradient(180deg, #8b7355 0%, #6d5a43 100%);
  border: 1px solid #d4af37;
  color: #f4e8d0;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  padding: 0.75rem 1.5rem;
  transition: all 0.2s ease;
}

.button-primary:hover {
  box-shadow: 0 0 12px rgba(212, 175, 55, 0.4);
  transform: translateY(-2px);
}

.button-primary:active {
  transform: translateY(0);
}
```

**Tooltips:**
```css
.tooltip {
  background: #f4e8d0;
  color: #2a1810;
  border: 1px solid #8b7355;
  box-shadow: 0 4px 12px rgba(0,0,0,0.6);
  padding: 0.75rem;
  font-family: 'Crimson Text', serif;
  max-width: 300px;
}
```

**Hover Effects:**
- Entity cards glow subtly: `box-shadow: 0 0 8px rgba(212, 175, 55, 0.3)`
- Smooth transitions: `transition: all 0.2s ease`
- Cursor changes to pointer on interactive elements
- Slight scale up on hover: `transform: scale(1.02)`

---

## PART 7: EXAMPLE CONVERSATION FLOWS

### Flow 1: Initial Upload

```
[Jim opens LMS for first time]

Gemini → Frontend:
{
  "text": "Welcome to your Lore Management System, Jim. I'm here to help organize 30 years of campaign history. \n\nLet's start by uploading some files. What would you like to add first?",
  "context": "dashboard",
  "data": {stats: {/* empty stats */}},
  "actions": [
    {"id": "upload", "label": "Upload Files"},
    {"id": "tour", "label": "Show Me Around"}
  ]
}

Jim: "Upload my Shadow Realm notes"

Gemini → Frontend:
{
  "text": "Great! Drop your Shadow Realm files here, or click to browse.",
  "context": "upload",
  "data": {}
}

[Jim drops 5 files]

Frontend → Gemini:
{
  "type": "files_selected",
  "files": ["session_47.txt", "npc_list.txt", ...]
}

Gemini (calls upload_files function):
→ {batch_id: "batch123", status: "processing", files_queued: 5}

Gemini → Frontend:
{
  "text": "Processing 5 files...",
  "context": "upload",
  "data": {
    queue: [
      {file: "session_47.txt", status: "processing"},
      ...
    ]
  }
}

[Processing completes]

Gemini → Frontend:
{
  "text": "Upload complete! Found 23 entities and 2 contradictions in the Shadow Realm files.\n\nWant to review the contradictions now or browse the entities first?",
  "context": "upload",
  "data": {
    stats: {
      files_processed: 5,
      entities_found: 23,
      contradictions: 2
    }
  },
  "actions": [
    {"id": "review_contradictions", "label": "Review Contradictions"},
    {"id": "browse_entities", "label": "Browse Entities"}
  ]
}
```

### Flow 2: Contradiction Resolution with Impact Preview

```
Jim: "Show me the contradictions"

Gemini (calls list_contradictions):
→ [2 contradictions found]

Gemini → Frontend:
{
  "text": "Here's the first contradiction - conflicting dates for the Shadow Realm siege:",
  "context": "contradiction",
  "data": {
    contradiction_id: "c001",
    type: "Temporal Discrepancy",
    severity: "HIGH",
    description: "Two different dates given for when the siege began",
    versions: [
      {
        id: "v1",
        text: "The siege began in year 302",
        source: "session_47.txt",
        confidence: "HIGH"
      },
      {
        id: "v2",
        text: "The siege started in year 304",
        source: "old_campaign_notes.txt",
        confidence: "MEDIUM"
      }
    ]
  }
}

[Jim clicks "Show Impact"]

Frontend → Gemini:
{
  "type": "action",
  "action_id": "preview_impact",
  "params": {contradiction_id: "c001"}
}

Gemini (calls preview_canon_decision("c001", "v1")):
→ {affected_entities: [...4 entities...], affected_count: 4}

Gemini → Frontend:
{
  "text": "If you choose year 302, this will update 4 related entities:",
  "context": "contradiction",
  "data": {
    ...previous data...,
    impact: {
      affected_count: 4,
      affected_entities: [
        {
          id: "e001",
          name: "The Black King",
          field: "first_appearance",
          old_value: "304",
          new_value: "302"
        },
        ...
      ]
    }
  }
}

[Jim reviews impact, clicks "Make A Canon"]

Frontend → Gemini:
{
  "type": "action",
  "action_id": "resolve",
  "params": {
    contradiction_id: "c001",
    canonical_version: "v1"
  }
}

Gemini (calls resolve_contradiction):
→ {success: true, updated_entities: 4}

Gemini → Frontend:
{
  "text": "✓ Marked year 302 as canonical. Updated 4 related entities.\n\nOne more contradiction remaining. Want to review it now?",
  "context": null,
  "actions": [
    {"id": "next_contradiction", "label": "Yes, Show Next"},
    {"id": "done", "label": "I'll Come Back Later"}
  ]
}
```

### Flow 3: Search with Filters and Undo

```
Jim: "Find all tavern keepers from the first campaign"

Gemini (calls search_entities):
→ {results: [...8 entities...], total_count: 8}

Gemini → Frontend:
{
  "text": "Found 8 tavern keepers from your first campaign:",
  "context": "search",
  "data": {
    query: "tavern keepers (first campaign)",
    results: [
      {
        canon_id: "npc-001",
        canonical_name: "Grimald the Innkeeper",
        type: "Character",
        confidence: "CONFIRMED",
        party_knowledge: "KNOWN"
      },
      ...
    ],
    filters: {
      active: {
        campaign_era: "1995-2000",
        type: ["Character"]
      }
    }
  }
}

[Jim clicks confidence filter: "CONFIRMED only"]

Frontend → Gemini:
{
  "type": "filter_change",
  "filters": {
    confidence: "CONFIRMED",
    campaign_era: "1995-2000",
    type: ["Character"]
  }
}

Gemini (calls search_entities with new filters):
→ {results: [...5 entities...], total_count: 5}

Gemini → Frontend:
{
  "text": "Filtered to 5 confirmed tavern keepers.",
  "context": "search",
  "data": {
    results: [...5 filtered entities...]
  }
}

[Jim accidentally bulk-updates party knowledge to UNKNOWN]

Jim: "Wait, undo that!"

Gemini (calls undo):
→ {success: true, restored_state: {...}}

Gemini → Frontend:
{
  "text": "✓ Undid bulk update. Restored party knowledge for 5 entities to KNOWN.",
  "context": "search",
  "data": {
    results: [...entities with restored state...]
  }
}
```

---

## PART 8: TECHNICAL IMPLEMENTATION

### Frontend Stack
- **Framework**: React (or vanilla JS if you prefer)
- **WebSocket**: For real-time Gemini communication
- **Styling**: CSS with Fantasy RPG aesthetic
- **State Management**: React Context or simple state
- **Build**: Vite or similar (fast dev experience)

### WebSocket Implementation
```javascript
// Connect to Gemini endpoint
const ws = new WebSocket('ws://localhost:8000/ws/gemini');

// Send user message
function sendMessage(text) {
  ws.send(JSON.stringify({
    type: 'user_message',
    text: text,
    current_context: currentContext,
    current_state: getCurrentState()
  }));
}

// Receive Gemini response
ws.onmessage = (event) => {
  const response = JSON.parse(event.data);
  
  // Add to chat history
  addMessage('gemini', response.text);
  
  // Update UI context
  if (response.context) {
    setContext(response.context);
    setContextData(response.data);
  }
  
  // Store available actions
  setAvailableActions(response.actions);
};

// Handle user actions
function handleAction(actionId, params) {
  ws.send(JSON.stringify({
    type: 'action',
    action_id: actionId,
    params: params
  }));
}

// Reconnection logic
ws.onclose = () => {
  setTimeout(() => {
    console.log('Reconnecting...');
    ws = new WebSocket('ws://localhost:8000/ws/gemini');
  }, 3000);
};
```

### Error Handling
```javascript
// Frontend should handle these gracefully
function handleError(error) {
  if (error.type === 'connection_lost') {
    showNotification('Connection lost. Reconnecting...', 'warning');
    attemptReconnect();
  } else if (error.type === 'api_error') {
    showNotification(`Error: ${error.message}`, 'error');
    // Show retry option
  } else if (error.type === 'validation_error') {
    showNotification('Please check your input', 'error');
    highlightInvalidFields(error.fields);
  }
}
```

---

## PART 9: BUILD PHASES

### Phase 1: Core Infrastructure (Days 1-2)
1. ✅ Basic HTML structure with Fantasy RPG aesthetic
2. ✅ Chat interface (messages, input, send)
3. ✅ WebSocket connection to Gemini
4. ✅ Message handling (send/receive)
5. ✅ Context switching system
6. ✅ Quick Actions bar with Undo button

### Phase 2: Essential Contexts (Days 3-4)
7. ✅ Upload context (drag-drop, queue, results)
8. ✅ Search context (entity grid, filters)
9. ✅ Contradiction context (card, impact preview)
10. ✅ Entity detail context

### Phase 3: Critical Features (Day 5)
11. ✅ Undo system (fully functional)
12. ✅ Impact preview (for contradictions)
13. ✅ Interactive filters (in search)
14. ✅ Bulk selection (in search)

### Phase 4: Polish & Testing (Day 6)
15. ✅ Loading states and animations
16. ✅ Error handling
17. ✅ Tooltips and hover effects
18. ✅ Keyboard shortcuts
19. ✅ Responsive adjustments
20. ✅ Dashboard context

---

## PART 10: SUCCESS CRITERIA

**MVP is complete when:**
- ✅ Jim can upload files and see them processed
- ✅ Jim can search entities with filters
- ✅ Jim can review and resolve contradictions with impact preview
- ✅ Jim can undo any action
- ✅ Jim can view entity details and relationships
- ✅ All interactions feel natural and conversational
- ✅ Fantasy RPG aesthetic is consistent throughout
- ✅ No major bugs or crashes

**Quality checks:**
- Response time < 2 seconds for all actions
- No UI jank or awkward transitions
- Tooltips are helpful and clear
- Error messages are friendly and actionable
- Undo works reliably for all actions
- Impact preview accurately shows consequences

---

## PART 11: FUTURE ENHANCEMENTS (Post-MVP)

**Phase 2 Features (Add based on usage):**
- Relationship graph visualization
- Timeline view
- Campaign organization
- Bulk edit operations
- Export options
- Mobile optimization

**Phase 3 Features (Advanced):**
- Voice input for conversations
- AI-assisted entity suggestions
- Cross-reference checker
- Collaborative features
- VTT integration
- Advanced visualizations

---

## APPENDIX: BACKEND ENDPOINTS REFERENCE

**Base URL:** `http://localhost:8000`

```
POST   /api/upload
  Body: FormData with files
  Response: {batch_id, status, files_queued}

GET    /api/entities?query=X&filters=Y
  Response: {results: Entity[], total_count}

GET    /api/entities/{canon_id}
  Response: Entity

GET    /api/contradictions?filters=X
  Response: Contradiction[]

GET    /api/contradictions/{id}
  Response: Contradiction

POST   /api/preview-canon-decision
  Body: {contradiction_id, chosen_version}
  Response: {affected_entities, affected_count}

POST   /api/contradictions/{id}/resolve
  Body: {canonical_version, reason}
  Response: {success, updated_entities}

POST   /api/bulk-update
  Body: {entity_ids, updates}
  Response: {success_count, failed_count}

GET    /api/dashboard
  Response: {stats object}

POST   /api/undo
  Response: {success, restored_state}

WS     /ws/gemini
  Bidirectional WebSocket for Gemini conversation
```

---

## FINAL NOTES FOR GEMINI

**You are building this system AND you are the system.**

As builder:
- Create clean, maintainable code
- Follow the Fantasy RPG aesthetic closely
- Implement all critical features (undo, impact, filters, quick actions)
- Test each feature as you build
- Make it feel smooth and responsive

As agent:
- Be helpful and encouraging
- Understand natural language flexibly
- Provide context-aware suggestions
- Never make canon decisions for Jim (Gospel Principle)
- Remember conversation context
- Make the system feel alive and intelligent

**The goal:** Make lore management feel like an adventure, not a chore. Jim should enjoy organizing 30 years of memories.

**Start with:** Chat interface + Upload context. Get the conversational foundation working first, then add visual contexts one by one.

Good luck! 🗡️📜✨
