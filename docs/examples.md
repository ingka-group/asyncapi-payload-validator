# Examples and Output Format

Detailed examples of validation output, real-world scenarios, and how to interpret results.

## CLI Output

### ✅ Passing Validation

When your payload matches the AsyncAPI schema perfectly:

```
➕ Attributes in JSON but not in YAML:
    ✔  None

❌ Attributes with type mismatches:
    ✔  None

🚫 Required attributes in YAML but missing in JSON:
    ✔  None

↔️  String length violations (minLength/maxLength):
    ✔  None

#️⃣  Pattern violations:
    ✔  None

✅ Enum violations:
    ✔  None

🔢 Numeric constraint violations:
    ✔  None

🧩 Composition (oneOf/anyOf/allOf) violations:
    ✔  None

✅ RESULT: PASS
```

**Exit code**: `0` (success)

---

### ❌ Failing Validation

When violations are detected:

```
➕ Attributes in JSON but not in YAML:
    ⚠️  metadata.extraField: attribute not declared
    ⚠️  unknownProperty: attribute not declared

❌ Attributes with type mismatches:
    ✖️  userId: expected string, got number
    ✖️  isActive: expected boolean, got string

🚫 Required attributes in YAML but missing in JSON:
    ⚠️  email: required but missing
    ⚠️  eventType: required but missing

↔️  String length violations (minLength/maxLength):
    ✖️  username: length 2 violates minLength 3

#️⃣  Pattern violations:
    ✖️  email: value 'invalid-email' does not match pattern ^[\w\.-]+@[\w\.-]+\.\w+$
    ✖️  phoneNumber: value 'abc123' does not match pattern ^\+?[1-9]\d{1,14}$

✅ Enum violations:
    ✖️  status: value 'pending' not in enum [active, inactive, suspended]
    ✖️  role: value 'superadmin' not in enum [user, admin, guest]

🔢 Numeric constraint violations:
    ✖️  age: value 5 is below minimum 18
    ✖️  count: value 7 is not a multiple of 5
    ✖️  price: value 10001 exceeds maximum 10000

🧩 Composition (oneOf/anyOf/allOf) violations:
    ✖️  contactInfo: oneOf expects exactly 1 match, got 0 matches

❌ RESULT: FAIL
```

**Exit code**: `1` (failure)

---

### 📄 HTML Report

When using `--html-report`, an HTML file is generated with:

- 📊 Visual summary with violation counts
- 🔍 Line-by-line code context from both payload and spec
- 🎨 Syntax-highlighted source code snippets
- 📱 Responsive design for easy viewing

---

## Real-World Example

### ❌ Failing Payload

```json
{
  "eventType": "OrderPlaced",
  "orderId": 12345,
  "customerEmail": "not-an-email",
  "amount": 5,
  "status": "pending",
  "extraField": "should not be here"
}
```

### ✅ Expected Schema

```yaml
payload:
  type: object
  required:
    - eventType
    - orderId
    - customerEmail
    - amount
    - currency
  properties:
    eventType:
      type: string
      enum: [OrderPlaced, OrderCancelled]
    orderId:
      type: string
      pattern: '^ORD-\d{6}$'
    customerEmail:
      type: string
      format: email
    amount:
      type: number
      minimum: 10
      maximum: 10000
    currency:
      type: string
      enum: [USD, EUR, GBP]
    status:
      type: string
      enum: [confirmed, processing]
```

### 🔍 Validation Results

```
➕ Attributes in JSON but not in YAML:
    ⚠️  extraField: attribute not declared

❌ Attributes with type mismatches:
    ✖️  orderId: expected string, got number

🚫 Required attributes in YAML but missing in JSON:
    ⚠️  currency: required but missing

↔️  String length violations (minLength/maxLength):
    ✔  None

#️⃣  Pattern violations:
    ✖️  orderId: value '12345' does not match pattern '^ORD-\d{6}$'
    ✖️  customerEmail: value 'not-an-email' does not match email format

✅ Enum violations:
    ✖️  status: value 'pending' not in enum [confirmed, processing]

🔢 Numeric constraint violations:
    ✖️  amount: value 5 is below minimum 10

🧩 Composition (oneOf/anyOf/allOf) violations:
    ✔  None

❌ RESULT: FAIL
```

### ✅ Corrected Payload

```json
{
  "eventType": "OrderPlaced",
  "orderId": "ORD-123456",
  "customerEmail": "customer@example.com",
  "amount": 99.99,
  "currency": "USD",
  "status": "confirmed"
}
```

**Validation Result**: `✅ RESULT: PASS`

---

## Understanding the Output

The validator uses clear icons to categorize findings:

| Icon | Category | Severity | Description |
|------|----------|----------|-------------|
| ➕ | Extra Attributes | WARN | Fields in your payload not defined in schema |
| ❌ | Type Mismatches | ERROR | Wrong data types (e.g., number instead of string) |
| 🚫 | Missing Required | ERROR | Required fields not present in payload |
| ↔️ | Length Violations | WARN | String too short/long (minLength/maxLength) |
| #️⃣ | Pattern Violations | ERROR | String doesn't match regex pattern |
| ✅ | Enum Violations | ERROR | Value not in allowed list |
| 🔢 | Numeric Violations | ERROR | Number constraints violated (min/max/multipleOf) |
| 🧩 | Composition Violations | ERROR | oneOf/anyOf/allOf rules not satisfied |

**Status Indicators:**
- `✔ None` — No violations in this category
- `⚠️` — Warning-level violation
- `✖️` — Error-level violation

---

## Quick Comparison: Pass vs Fail

| Aspect | ✅ Passing | ❌ Failing |
|--------|-----------|-----------|
| **Output** | All categories show `✔ None` | Categories show `⚠️` or `✖️` violations |
| **Exit Code** | `0` | `1` |
| **Console** | `✅ RESULT: PASS` in green | `❌ RESULT: FAIL` in red |
| **HTML Report** | Optional with `--html-report` | Optional with `--html-report` |
| **CI/CD** | Pipeline continues ✓ | Pipeline fails ✗ |

---

## Example Files

### Example Payload

```json
{
  "eventType": "UserSignedUp",
  "userId": "12345",
  "email": "user@example.com",
  "metadata": {
    "source": "mobile-app",
    "version": "2.1.0"
  }
}
```

### Example AsyncAPI Spec

```yaml
asyncapi: 2.6.0
info:
  title: User Events API
  version: 1.0.0

channels:
  user/signedup:
    subscribe:
      message:
        messageId: UserSignedUp
        payload:
          type: object
          required:
            - eventType
            - userId
            - email
          properties:
            eventType:
              type: string
              enum: [UserSignedUp, UserDeleted]
            userId:
              type: string
              pattern: '^\d+$'
            email:
              type: string
              format: email
            metadata:
              type: object
              additionalProperties: true
```
