# Firestore Indexes Required for GradMate AI

This document lists all the composite indexes that need to be created in the Firebase Console for the application to work properly.

## Required Indexes

### 1. Study Plans Collection
**Collection:** `study_plans`
- **Fields:** `user_id` (Ascending), `created_on` (Ascending)
- **Purpose:** For ordering study plans by creation date for a specific user
- **Usage:** Student dashboard, study planner

### 2. Placement Drives Collection
**Collection:** `placement_drives`
- **Fields:** `posted_by` (Ascending), `created_at` (Ascending)
- **Purpose:** For ordering drives by creation date for a specific officer
- **Usage:** Officer drives management

### 3. Training Resources Collection
**Collection:** `training_resources`
- **Fields:** `uploaded_by` (Ascending), `upload_date` (Ascending)
- **Purpose:** For ordering training materials by upload date for a specific officer
- **Usage:** Officer training management

### 4. Messages Collection
**Collection:** `messages`
- **Fields:** `sender_id` (Ascending), `timestamp` (Ascending)
- **Purpose:** For ordering messages by timestamp for a specific sender
- **Usage:** Message history, chat functionality

### 5. Messages Collection (Alternative)
**Collection:** `messages`
- **Fields:** `receiver_id` (Ascending), `timestamp` (Ascending)
- **Purpose:** For ordering messages by timestamp for a specific receiver
- **Usage:** Message history, chat functionality

### 6. AI Usage Collection
**Collection:** `ai_usage`
- **Fields:** `user_id` (Ascending), `timestamp` (Ascending)
- **Purpose:** For tracking AI usage by user and time
- **Usage:** Analytics, usage tracking

## How to Create Indexes

1. Go to the Firebase Console
2. Navigate to Firestore Database
3. Click on the "Indexes" tab
4. Click "Create Index"
5. Select the collection name
6. Add the required fields in the specified order
7. Set the field order (Ascending/Descending) as specified
8. Click "Create"

## Notes

- All queries in the application have been optimized to avoid unnecessary ordering
- Where ordering is required, it's done in Python after fetching the data
- The indexes listed above are only needed if you want to enable server-side ordering for better performance
- Single-field indexes are automatically created by Firestore and don't need manual creation

## Performance Considerations

- Creating these indexes will improve query performance for large datasets
- Without these indexes, the application will still work but may be slower with large amounts of data
- Consider the cost implications of maintaining these indexes in production