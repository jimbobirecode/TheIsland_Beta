
# 🧠 Intelligent Email Parsing - Learning System

## Overview

Your email parsing system now **learns from real-world data** and improves over time. It tracks every parse, identifies mistakes, and helps you understand what's working.

---

## 🎯 What It Does

### **1. Tracks Every Parse**
- Logs all extracted data (dates, players, intent, lodging)
- Records confidence scores
- Saves email snippets for debugging
- Timestamps everything

### **2. Learns From Corrections**
- When you mark parses as correct/incorrect
- Identifies common failure patterns
- Suggests new regex patterns
- Builds dataset for future improvements

### **3. Flags Low-Confidence Parses**
- Automatically identifies parses that might be wrong
- Creates review queue for staff
- Prioritizes by confidence score

### **4. Reports Accuracy**
- Shows success rate over time
- Breaks down by confidence level
- Tracks improvement trends

---

## 📊 Quick Start

### View Current Accuracy

```bash
python parsing_dashboard.py report
```

**Output:**
```
📊 PARSING ACCURACY REPORT
================================================================================

📅 Last 7 days:
   Total emails parsed:  45
   Verified (confirmed): 32
   ✅ Correct:            29 (90.6%)
   ❌ Incorrect:          3
   📊 Avg confidence:     0.72
   🔼 High confidence (>0.7): 35
   🔽 Low confidence (<0.5):  8

🔍 COMMON FAILURE PATTERNS
   • date_mismatch:       2 (66.7%)
   • player_count_mismatch: 1 (33.3%)
```

---

### Interactive Dashboard

```bash
python parsing_dashboard.py
```

**Menu Options:**
1. View Accuracy Report
2. View Failure Patterns
3. Review Low-Confidence Parses
4. View Pattern Suggestions
5. Submit Correction
6. Export Stats (JSON)
7. Exit

---

## 🔧 Integration with Email Bot

### **Step 1: Track Parsing Results**

Add to `island_email_bot.py` after parsing:

```python
from parsing_intelligence import track_parsing

# After parsing email
parsed = parse_email_enhanced(subject, body, sender_email, sender_name)

# Track the result
track_parsing(
    email_id=message_id,
    booking_id=booking_id,
    entity=parsed,  # The BookingEntity object
    email_body=body
)
```

### **Step 2: Mark Correct Parses**

When customer confirms booking:

```python
from parsing_intelligence import mark_correct

# Customer confirmed booking
if is_confirmation_email(subject, body):
    mark_correct(booking_id)
```

### **Step 3: Submit Corrections**

When staff notices a parsing error:

```python
from parsing_intelligence import submit_correction

# Staff corrects the booking
submit_correction(
    booking_id="ISL-20251213-ABC123",
    actual_dates=["2026-04-15", "2026-04-16"],
    actual_players=8,  # Was parsed as 4
    source="staff_dashboard"
)
```

---

## 📈 Real-World Workflow

### **Daily:**
1. System automatically tracks all parses
2. Low-confidence parses flagged for review
3. Staff reviews flagged parses in dashboard

### **Weekly:**
```bash
python parsing_dashboard.py report > weekly_report.txt
```
- Review accuracy trends
- Check failure patterns
- Submit corrections for mistakes

### **Monthly:**
1. Export stats: `parsing_dashboard.py` → Option 6
2. Analyze learned patterns
3. Update regex patterns based on failures
4. Re-run test suite to verify improvements

---

## 🎓 Learning Mechanisms

### **1. Automatic Correction Detection**

When a customer **confirms** a booking:
```python
# Customer replies "Yes, confirmed"
→ System marks parsing as CORRECT
→ Confidence in similar patterns increases
```

### **2. Staff Corrections**

When staff fixes a booking:
```python
# Staff changes 4 players → 8 players
→ System logs the mistake
→ Analyzes email snippet
→ Suggests new pattern: "group of 8 golfers"
```

### **3. Pattern Suggestions**

After collecting failures:
```bash
python parsing_dashboard.py
→ Option 4: View Pattern Suggestions

Output:
   Found 5 date parsing failures
   Example: "Can we book for the weekend of April 15th?"
   → Suggest pattern: r'weekend of (\w+ \d+)'
```

---

## 📊 Data Storage

### Files Created

```
parsing_data/
├── parsing_feedback.jsonl     # All parsing results (append-only)
├── parsing_stats.json          # Running statistics
└── learned_patterns.json       # Mistakes and corrections
```

### Format: `parsing_feedback.jsonl`

Each line is a JSON object:
```json
{
  "email_id": "msg_12345",
  "booking_id": "ISL-20251213-ABC123",
  "timestamp": "2025-12-13T16:30:00",
  "extracted_dates": ["2026-04-15"],
  "extracted_players": 4,
  "extracted_intent": "booking_request",
  "extracted_lodging": false,
  "confidence_score": 0.85,
  "email_snippet": "Hi, can we book for April 15? Party of 4...",
  "was_correct": true,
  "correction_source": "customer_confirmation"
}
```

---

## 🚀 Advanced: Custom Model Training

### **When You Have 100+ Corrections**

1. **Export labeled data:**
```python
from parsing_intelligence import learning_system

# Get all corrections
corrections = [
    fb for fb in learning_system._read_all_feedback()
    if fb['was_correct'] is False
]
```

2. **Train custom patterns:**
```python
# Analyze common mistakes
date_errors = [c for c in corrections if 'date' in c['mistake_types']]

# Extract unique patterns
patterns = set()
for error in date_errors:
    snippet = error['email_snippet']
    # Analyze what was missed
    # Add new regex patterns
```

3. **A/B Test:**
```python
# Test new patterns on 10% of traffic
if random.random() < 0.1:
    result = new_parser.parse(email)
else:
    result = current_parser.parse(email)

# Compare results
```

---

## 💡 Example Improvements Over Time

### **Week 1:**
```
Accuracy: 62.5% (test suite)
Real-world: Unknown (no tracking)
```

### **Week 4 (100 emails):**
```
Accuracy: 85% (verified bookings)
Identified failures:
- "Group of 8 golfers" → parsed as 4 (golf term priority)
- "Weekend of April 15" → missed date
→ Fixed both patterns
```

### **Week 12 (500 emails):**
```
Accuracy: 92%
New patterns added: 8
Average confidence: 0.78
Low-confidence reviews: 2-3 per week
```

---

## 📝 API Reference

### Track Parsing
```python
track_parsing(email_id, booking_id, entity, email_body)
```

### Mark Correct
```python
mark_correct(booking_id)
```

### Submit Correction
```python
submit_correction(
    booking_id,
    actual_dates=None,
    actual_players=None,
    actual_intent=None,
    actual_lodging=None,
    source="staff"
)
```

### Get Accuracy
```python
accuracy = get_accuracy()  # Returns dict with metrics
```

### Get Review Queue
```python
to_review = get_review_queue()  # Returns low-confidence parses
```

---

## 🎯 Success Metrics

### **Target Goals:**

| Metric | Current | 1 Month | 3 Months |
|--------|---------|---------|----------|
| **Accuracy** | 62.5% | 80% | 90% |
| **Avg Confidence** | 0.65 | 0.75 | 0.85 |
| **Manual Reviews** | N/A | <10/week | <5/week |
| **New Patterns** | 0 | 5-8 | 15-20 |

---

## 🔒 Privacy & Data

- **Email snippets**: Only first 200 characters stored
- **No PII**: Customer names/emails not in learning data
- **Local storage**: All data in `parsing_data/` folder
- **GDPR**: Can delete individual booking data on request

---

## 🎉 Benefits

### **Before (Static System):**
- ❌ No idea if parses are accurate
- ❌ Mistakes repeat forever
- ❌ No improvement over time
- ❌ Manual pattern updates only

### **After (Learning System):**
- ✅ Track accuracy in real-time
- ✅ Learn from every mistake
- ✅ Automatic pattern suggestions
- ✅ Continuously improving
- ✅ Data-driven decisions

---

## 🚀 Next Steps

1. **Integrate tracking** into email bot (5 lines of code)
2. **Run for 1 week** to collect data
3. **Review dashboard** to see patterns
4. **Submit corrections** for any mistakes
5. **Watch accuracy improve** over time

---

## 📞 Support

**View logs:**
```bash
tail -f parsing_data/parsing_feedback.jsonl
```

**Reset data** (start fresh):
```bash
rm -rf parsing_data/
```

**Export for analysis:**
```bash
python parsing_dashboard.py
→ Option 6: Export Stats
```

---

**Bottom line:** Your system now learns from real production emails and gets smarter over time! 🧠
