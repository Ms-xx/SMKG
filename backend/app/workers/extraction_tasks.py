from app.core.celery_app import celery_app


@celery_app.task(name="extract_entities", bind=True, queue="extraction")
def extract_entities_task(self, document_id: str):
    try:
        self.update_state(state="PROGRESS", meta={"progress": 10, "step": "loading_document"})
        self.update_state(state="PROGRESS", meta={"progress": 50, "step": "extracting_entities"})
        self.update_state(state="PROGRESS", meta={"progress": 80, "step": "extracting_relations"})
        self.update_state(state="PROGRESS", meta={"progress": 100, "step": "completed"})
        return {"status": "success", "document_id": document_id}
    except Exception as e:
        self.update_state(state="FAILURE", meta={"error": str(e)})
        raise


@celery_app.task(name="extract_build_knowledge_graph_stub", bind=True, queue="extraction")
def build_knowledge_graph_task(self, document_id: str):
    try:
        self.update_state(state="PROGRESS", meta={"progress": 50, "step": "building_graph"})
        self.update_state(state="PROGRESS", meta={"progress": 100, "step": "completed"})
        return {"status": "success", "document_id": document_id}
    except Exception as e:
        self.update_state(state="FAILURE", meta={"error": str(e)})
        raise
