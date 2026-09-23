-- ============================================================
-- XiangMu 步骤 10.1：性能索引（存量 MySQL 库手动执行）
-- 说明：Base.metadata.create_all() 不会给已存在的表加索引/加列。
-- 新库会自动带上 document.py 中声明的 Index；存量库需手动执行本脚本。
-- 请在 wx 库执行：
--   mysql -uroot -p < backend/sql/idx_performance.sql
-- 均使用 IF NOT EXISTS，可重复执行。
-- ============================================================

USE `wx`;

-- documents：按归属人/状态/创建时间查询加速（列表页、个人文档）
ALTER TABLE `documents` ADD INDEX IF NOT EXISTS `ix_documents_uploaded_by` (`uploaded_by`);
ALTER TABLE `documents` ADD INDEX IF NOT EXISTS `ix_documents_status` (`status`);
ALTER TABLE `documents` ADD INDEX IF NOT EXISTS `ix_documents_created_at` (`created_at`);

-- document_pages：详情页按 (document_id, page_number) 拉取页面加速
ALTER TABLE `document_pages` ADD INDEX IF NOT EXISTS `ix_pages_doc_page` (`document_id`, `page_number`);
ALTER TABLE `document_pages` ADD INDEX IF NOT EXISTS `ix_pages_document_id` (`document_id`);

-- document_elements：单页元素加载加速
ALTER TABLE `document_elements` ADD INDEX IF NOT EXISTS `ix_elements_page_id` (`page_id`);
ALTER TABLE `document_elements` ADD INDEX IF NOT EXISTS `ix_elements_type` (`element_type`);

-- tasks：按文档/负责人/状态与类型查询加速
ALTER TABLE `tasks` ADD INDEX IF NOT EXISTS `ix_tasks_document_id` (`document_id`);
ALTER TABLE `tasks` ADD INDEX IF NOT EXISTS `ix_tasks_assigned_status` (`assigned_to`, `status`);

-- annotations：按文档/标注人/状态聚合（工作量统计）加速
ALTER TABLE `annotations` ADD INDEX IF NOT EXISTS `ix_annotations_document_id` (`document_id`);
ALTER TABLE `annotations` ADD INDEX IF NOT EXISTS `ix_annotations_annotator_status` (`annotated_by`, `status`);