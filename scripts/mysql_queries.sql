-- MySQLでpocchipのデータ構造を調査するクエリ

-- 1. データベースの基本情報
SELECT DATABASE();

-- 2. テーブル一覧を確認
SHOW TABLES;

-- 3. Pochipp関連のカスタム投稿タイプを確認
SELECT DISTINCT post_type, COUNT(*) as count
FROM wp_posts 
WHERE post_type LIKE '%pochipp%' 
   OR post_type LIKE '%product%'
   OR post_type LIKE '%item%'
GROUP BY post_type
ORDER BY count DESC;

-- 4. 全ての投稿タイプを確認（上位20件）
SELECT DISTINCT post_type, COUNT(*) as count
FROM wp_posts 
GROUP BY post_type
ORDER BY count DESC
LIMIT 20;

-- 5. Pochipp関連のメタキーを確認
SELECT DISTINCT meta_key, COUNT(*) as usage_count
FROM wp_postmeta 
WHERE meta_key LIKE '%pochipp%'
   OR meta_key LIKE '%amazon%'
   OR meta_key LIKE '%rakuten%'
   OR meta_key LIKE '%yahoo%'
ORDER BY usage_count DESC
LIMIT 20;

-- 6. Pochipp関連のタクソノミーを確認
SELECT DISTINCT taxonomy, COUNT(*) as term_count
FROM wp_term_taxonomy 
WHERE taxonomy LIKE '%pochipp%'
   OR taxonomy LIKE '%product%'
   OR taxonomy LIKE '%item%'
GROUP BY taxonomy
ORDER BY term_count DESC;
