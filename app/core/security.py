"""
Security context and identifier management.
Ensures user_id, company_id, dataset_id, version, workflow_id, and thread_id
remain strictly distinct, laying the groundwork for Phase 9 and 10 authorization.
"""
from typing import Optional
from pydantic import BaseModel, Field
import uuid


class AuthContext(BaseModel):
    """
    Context model maintaining distinct scopes and identifiers.
    Prevents confusing workflow_id with thread_id or company_id with dataset_id.
    """
    user_id: str = Field(default="usr_local_analyst", description="Authenticated user/principal")
    company_id: Optional[str] = Field(default=None, description="Active company scope")
    dataset_id: Optional[str] = Field(default=None, description="Active dataset identifier")
    dataset_version: Optional[int] = Field(default=None, description="Immutable dataset version")
    workflow_id: Optional[str] = Field(default=None, description="Business run/status identifier")
    thread_id: Optional[str] = Field(default=None, description="LangGraph execution checkpoint thread")

    def authorize_company_access(self, target_company_id: str) -> None:
        """
        Enforces tenant / company authorization boundary.
        Raises PermissionError if principal does not have access.
        """
        if not target_company_id or not isinstance(target_company_id, str):
            raise ValueError("Invalid target_company_id provided for authorization check.")
        
        # When context is locked to a specific company, prohibit access to others
        if self.company_id and self.company_id != target_company_id:
            raise PermissionError(
                f"Unauthorized company access: Context principal '{self.user_id}' "
                f"is bound to '{self.company_id}' but attempted access to '{target_company_id}'."
            )

    def authorize_dataset_access(self, target_dataset_id: str, target_version: Optional[int] = None) -> None:
        """
        Enforces dataset and version immutability boundary.
        """
        if not target_dataset_id or not isinstance(target_dataset_id, str):
            raise ValueError("Invalid target_dataset_id provided for authorization check.")
        
        if self.dataset_id and self.dataset_id != target_dataset_id:
            raise PermissionError(
                f"Unauthorized dataset access: Context principal '{self.user_id}' "
                f"is bound to '{self.dataset_id}' but attempted access to '{target_dataset_id}'."
            )

        if self.dataset_version is not None and target_version is not None:
            if self.dataset_version != target_version:
                raise PermissionError(
                    f"Unauthorized version access: Context locked to version {self.dataset_version} "
                    f"cannot modify or access target version {target_version}."
                )

    @classmethod
    def create_default(
        cls,
        company_id: Optional[str] = None,
        dataset_id: Optional[str] = None,
        dataset_version: Optional[int] = None,
    ) -> "AuthContext":
        """Instantiates default single-user context."""
        return cls(
            user_id="usr_local_analyst",
            company_id=company_id,
            dataset_id=dataset_id,
            dataset_version=dataset_version,
            workflow_id=f"wf_{uuid.uuid4().hex[:12]}",
            thread_id=f"th_{uuid.uuid4().hex[:12]}",
        )
