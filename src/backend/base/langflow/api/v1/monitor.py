from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete
from sqlmodel import Session, col, select

from langflow.schema.message import MessageResponse
from langflow.services.auth.utils import get_current_active_user
from langflow.services.database.models.message.model import MessageRead, MessageTable, MessageUpdate
from langflow.services.database.models.transactions.crud import get_transactions_by_flow_id
from langflow.services.database.models.transactions.model import TransactionReadResponse
from langflow.services.database.models.user.model import User
from langflow.services.database.models.vertex_builds.crud import (
    delete_vertex_builds_by_flow_id,
    get_vertex_builds_by_flow_id,
)
from langflow.services.database.models.vertex_builds.model import VertexBuildMapModel
from langflow.services.deps import get_session

router = APIRouter(prefix="/monitor", tags=["Monitor"])


@router.get("/builds", response_model=VertexBuildMapModel)
async def get_vertex_builds(
    flow_id: Annotated[UUID, Query()],
    session: Annotated[Session, Depends(get_session)],
):
    try:
        vertex_builds = get_vertex_builds_by_flow_id(session, flow_id)
        return VertexBuildMapModel.from_list_of_dicts(vertex_builds)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/builds", status_code=204)
async def delete_vertex_builds(
    flow_id: Annotated[UUID, Query()],
    session: Annotated[Session, Depends(get_session)],
):
    try:
        delete_vertex_builds_by_flow_id(session, flow_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/messages", response_model=list[MessageResponse])
async def get_messages(
    session: Annotated[Session, Depends(get_session)],
    flow_id: Annotated[str | None, Query()] = None,
    session_id: Annotated[str | None, Query()] = None,
    sender: Annotated[str | None, Query()] = None,
    sender_name: Annotated[str | None, Query()] = None,
    order_by: Annotated[str | None, Query()] = "timestamp",
):
    try:
        stmt = select(MessageTable)
        if flow_id:
            stmt = stmt.where(MessageTable.flow_id == flow_id)
        if session_id:
            stmt = stmt.where(MessageTable.session_id == session_id)
        if sender:
            stmt = stmt.where(MessageTable.sender == sender)
        if sender_name:
            stmt = stmt.where(MessageTable.sender_name == sender_name)
        if order_by:
            col = getattr(MessageTable, order_by).asc()
            stmt = stmt.order_by(col)
        messages = session.exec(stmt)
        return [MessageResponse.model_validate(d, from_attributes=True) for d in messages]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/messages", status_code=204)
async def delete_messages(
    message_ids: list[UUID],
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    try:
        session.exec(delete(MessageTable).where(MessageTable.id.in_(message_ids)))  # type: ignore[attr-defined]
        session.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.put("/messages/{message_id}", response_model=MessageRead)
async def update_message(
    message_id: UUID,
    message: MessageUpdate,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(get_current_active_user)],
):
    try:
        db_message = session.get(MessageTable, message_id)
        if not db_message:
            raise HTTPException(status_code=404, detail="Message not found")
        message_dict = message.model_dump(exclude_unset=True, exclude_none=True)
        db_message.sqlmodel_update(message_dict)
        session.add(db_message)
        session.commit()
        session.refresh(db_message)
        return db_message
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.patch("/messages/session/{old_session_id}", response_model=list[MessageResponse])
async def update_session_id(
    old_session_id: str,
    new_session_id: Annotated[str, Query(..., description="The new session ID to update to")],
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    try:
        # Get all messages with the old session ID
        stmt = select(MessageTable).where(MessageTable.session_id == old_session_id)
        messages = session.exec(stmt).all()

        if not messages:
            raise HTTPException(status_code=404, detail="No messages found with the given session ID")

        # Update all messages with the new session ID
        for message in messages:
            message.session_id = new_session_id

        session.add_all(messages)

        session.commit()
        message_responses = []
        for message in messages:
            session.refresh(message)
            message_responses.append(MessageResponse.model_validate(message, from_attributes=True))
        return message_responses
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/messages/session/{session_id}", status_code=204)
async def delete_messages_session(
    session_id: str,
    session: Annotated[Session, Depends(get_session)],
):
    try:
        session.exec(
            delete(MessageTable)
            .where(col(MessageTable.session_id) == session_id)
            .execution_options(synchronize_session="fetch")
        )
        session.commit()
        return {"message": "Messages deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/transactions", response_model=list[TransactionReadResponse])
async def get_transactions(
    flow_id: Annotated[UUID, Query()],
    session: Annotated[Session, Depends(get_session)],
):
    try:
        transactions = get_transactions_by_flow_id(session, flow_id)
        return [
            TransactionReadResponse(
                transaction_id=t.id,
                timestamp=t.timestamp,
                vertex_id=t.vertex_id,
                target_id=t.target_id,
                inputs=t.inputs,
                outputs=t.outputs,
                status=t.status,
                error=t.error,
                flow_id=t.flow_id,
            )
            for t in transactions
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
