# 🔥 Firestore Indexes Configuration Guide

This guide helps you set up the required Firestore indexes to prevent "The query requires an index" errors in GradMate AI.

## 📋 Required Indexes

### 1. Users Collection Indexes

#### Index for User Authentication
- **Collection**: `users`
- **Fields**: 
  - `email` (Ascending)
  - `user_type` (Ascending)
- **Query**: `where('email', '==', email).where('user_type', '==', user_type)`

#### Index for Student Filtering
- **Collection**: `users`
- **Fields**:
  - `user_type` (Ascending)
  - `department` (Ascending)
  - `cgpa` (Ascending)
- **Query**: `where('user_type', '==', 'student').where('department', '==', dept).where('cgpa', '>=', min_cgpa)`

### 2. Study Plans Collection Indexes

#### Index for User Study Plans
- **Collection**: `study_plans`
- **Fields**:
  - `user_id` (Ascending)
  - `created_on` (Descending)
- **Query**: `where('user_id', '==', user_id).orderBy('created_on', 'desc')`

### 3. Placement Drives Collection Indexes

#### Index for Officer's Posted Drives
- **Collection**: `placement_drives`
- **Fields**:
  - `posted_by` (Ascending)
  - `created_at` (Descending)
- **Query**: `where('posted_by', '==', user_id).orderBy('created_at', 'desc')`

#### Index for Active Drives
- **Collection**: `placement_drives`
- **Fields**:
  - `last_date_to_apply` (Ascending)
- **Query**: `orderBy('last_date_to_apply', 'asc')`

### 4. Applications Collection Indexes

#### Index for Student Applications
- **Collection**: `applications`
- **Fields**:
  - `student_id` (Ascending)
  - `drive_id` (Ascending)
- **Query**: `where('student_id', '==', user_id).where('drive_id', '==', drive_id)`

#### Index for Drive Applications
- **Collection**: `applications`
- **Fields**:
  - `drive_id` (Ascending)
  - `applied_at` (Descending)
- **Query**: `where('drive_id', '==', drive_id).orderBy('applied_at', 'desc')`

### 5. Training Materials Collection Indexes

#### Index for Officer's Training Materials
- **Collection**: `training_materials`
- **Fields**:
  - `uploaded_by` (Ascending)
  - `upload_date` (Descending)
- **Query**: `where('uploaded_by', '==', user_id).orderBy('upload_date', 'desc')`

### 6. Messages Collection Indexes

#### Index for User Messages
- **Collection**: `messages`
- **Fields**:
  - `sender_id` (Ascending)
  - `receiver_id` (Ascending)
  - `timestamp` (Ascending)
- **Query**: Messages between two users, sorted by timestamp

### 7. AI Usage Collection Indexes

#### Index for User AI Usage
- **Collection**: `ai_usage`
- **Fields**:
  - `user_id` (Ascending)
  - `timestamp` (Descending)
- **Query**: `where('user_id', '==', user_id).orderBy('timestamp', 'desc')`

## 🚀 How to Create Indexes

### Method 1: Firebase Console (Recommended)

1. Go to [Firebase Console](https://console.firebase.google.com)
2. Select your project
3. Go to **Firestore Database** → **Indexes** tab
4. Click **Create Index**
5. Fill in the collection and fields as specified above
6. Click **Create**

### Method 2: Firebase CLI

1. Install Firebase CLI:
   ```bash
   npm install -g firebase-tools
   ```

2. Login to Firebase:
   ```bash
   firebase login
   ```

3. Initialize Firebase in your project:
   ```bash
   firebase init firestore
   ```

4. Create `firestore.indexes.json`:
   ```json
   {
     "indexes": [
       {
         "collectionGroup": "users",
         "queryScope": "COLLECTION",
         "fields": [
           { "fieldPath": "email", "order": "ASCENDING" },
           { "fieldPath": "user_type", "order": "ASCENDING" }
         ]
       },
       {
         "collectionGroup": "users",
         "queryScope": "COLLECTION",
         "fields": [
           { "fieldPath": "user_type", "order": "ASCENDING" },
           { "fieldPath": "department", "order": "ASCENDING" },
           { "fieldPath": "cgpa", "order": "ASCENDING" }
         ]
       },
       {
         "collectionGroup": "study_plans",
         "queryScope": "COLLECTION",
         "fields": [
           { "fieldPath": "user_id", "order": "ASCENDING" },
           { "fieldPath": "created_on", "order": "DESCENDING" }
         ]
       },
       {
         "collectionGroup": "placement_drives",
         "queryScope": "COLLECTION",
         "fields": [
           { "fieldPath": "posted_by", "order": "ASCENDING" },
           { "fieldPath": "created_at", "order": "DESCENDING" }
         ]
       },
       {
         "collectionGroup": "applications",
         "queryScope": "COLLECTION",
         "fields": [
           { "fieldPath": "student_id", "order": "ASCENDING" },
           { "fieldPath": "drive_id", "order": "ASCENDING" }
         ]
       },
       {
         "collectionGroup": "applications",
         "queryScope": "COLLECTION",
         "fields": [
           { "fieldPath": "drive_id", "order": "ASCENDING" },
           { "fieldPath": "applied_at", "order": "DESCENDING" }
         ]
       },
       {
         "collectionGroup": "training_materials",
         "queryScope": "COLLECTION",
         "fields": [
           { "fieldPath": "uploaded_by", "order": "ASCENDING" },
           { "fieldPath": "upload_date", "order": "DESCENDING" }
         ]
       },
       {
         "collectionGroup": "messages",
         "queryScope": "COLLECTION",
         "fields": [
           { "fieldPath": "sender_id", "order": "ASCENDING" },
           { "fieldPath": "receiver_id", "order": "ASCENDING" },
           { "fieldPath": "timestamp", "order": "ASCENDING" }
         ]
       },
       {
         "collectionGroup": "ai_usage",
         "queryScope": "COLLECTION",
         "fields": [
           { "fieldPath": "user_id", "order": "ASCENDING" },
           { "fieldPath": "timestamp", "order": "DESCENDING" }
         ]
       }
     ]
   }
   ```

5. Deploy indexes:
   ```bash
   firebase deploy --only firestore:indexes
   ```

## ⚠️ Important Notes

### Index Building Time
- **Small collections** (< 1M documents): 1-5 minutes
- **Medium collections** (1M-10M documents): 5-30 minutes
- **Large collections** (> 10M documents): 30+ minutes

### Index Costs
- Creating indexes is **free**
- Indexes consume **storage space** (minimal)
- No additional **read/write costs**

### Best Practices
1. **Create indexes before going live** to avoid user-facing errors
2. **Monitor index usage** in Firebase Console
3. **Remove unused indexes** to save storage
4. **Test queries** in development environment first

## 🔍 Troubleshooting

### Common Index Errors

#### Error: "The query requires an index"
**Solution**: Create the missing index as specified above

#### Error: "Index is still building"
**Solution**: Wait for the index to finish building (check Firebase Console)

#### Error: "Too many indexes"
**Solution**: Remove unused indexes or optimize your queries

### Performance Tips

1. **Limit query results** using `.limit()`
2. **Use pagination** for large datasets
3. **Avoid complex composite queries** when possible
4. **Cache frequently accessed data** in your application

## 📱 Testing Indexes

After creating indexes, test your queries:

1. **Student Dashboard**: Check if tasks load without errors
2. **Officer Dashboard**: Verify drives and applications display correctly
3. **Student Filter**: Test filtering by department, CGPA, skills
4. **Messaging**: Ensure messages load between users

## 🆘 Need Help?

If you encounter persistent index issues:

1. Check the **Firebase Console** → **Firestore** → **Indexes** tab
2. Look for **failed indexes** or **building indexes**
3. Review the **error logs** in Firebase Console
4. Ensure your **Firestore rules** allow the queries
5. Verify the **collection names** match exactly

---

**🎯 Remember**: Proper index setup is crucial for a smooth user experience. Create all required indexes before deploying to production! 