-- Rollback: Remove Circular Publishing System

-- 1. Drop notifications table
DROP TABLE IF EXISTS notifications CASCADE;

-- 2. Remove document_url column from circulars table
ALTER TABLE circulars DROP COLUMN IF EXISTS document_url;

-- 3. Drop storage policies for circulars bucket
DROP POLICY IF EXISTS "Allow Public Uploads to Circulars" ON storage.objects;
DROP POLICY IF EXISTS "Allow Public Access to Circulars" ON storage.objects;

-- 4. Delete circulars bucket (optional - only if you want to remove all circular documents)
-- DELETE FROM storage.buckets WHERE id = 'circulars';

-- Note: If you want to keep existing circulars but just remove the notification system,
-- comment out step 2 and step 4.
