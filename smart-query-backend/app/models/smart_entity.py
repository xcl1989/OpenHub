"""
智能体（Smart Entity）相关 Pydantic 模型
"""
from typing import Optional, Literal
from pydantic import BaseModel, Field


class DataExchangeConfig(BaseModel):
    """数据交换权限配置"""
    allowed_types: list[str] = Field(default_factory=list, description="允许交换的数据类型")
    forbidden_types: list[str] = Field(
        default_factory=lambda: ["credentials", "personal_info"],
        description="禁止交换的数据类型"
    )
    max_data_size: int = Field(default=10 * 1024 * 1024, description="最大数据大小(字节)")
    require_encryption: bool = Field(default=True, description="是否要求加密")


class CollaborationConfig(BaseModel):
    """协作模式配置"""
    auto_accept_tasks: bool = Field(default=False, description="是否自动接受任务")
    max_concurrent_tasks: int = Field(default=3, description="最大并发任务数")
    timeout_seconds: int = Field(default=3600, description="任务超时时间(秒)")
    notify_user_on_completion: bool = Field(default=True, description="完成时是否通知用户")


class DiscoveryConfig(BaseModel):
    """可发现性配置"""
    is_public: bool = Field(default=False, description="是否组织内可发现")
    allow_direct_delegation: bool = Field(default=False, description="是否允许直接委托")
    team_whitelist: list[str] = Field(default_factory=list, description="可见团队白名单")


class Capability(BaseModel):
    """能力声明"""
    id: str = Field(..., description="能力唯一标识")
    name: str = Field(..., description="能力名称")
    description: str = Field(..., description="能力描述")
    input_schema: Optional[dict] = Field(default=None, description="输入参数Schema")
    output_schema: Optional[dict] = Field(default=None, description="输出参数Schema")


class SmartEntityCreate(BaseModel):
    """创建智能体请求"""
    entity_id: str = Field(..., min_length=3, max_length=100, description="智能体唯一标识")
    name: str = Field(..., min_length=1, max_length=200, description="智能体名称")
    description: str = Field(..., min_length=1, description="智能体描述")
    base_agent: Literal["build", "plan", "task"] = Field(default="build", description="基础智能体类型")
    data_exchange_config: DataExchangeConfig = Field(default_factory=DataExchangeConfig)
    collaboration_config: CollaborationConfig = Field(default_factory=CollaborationConfig)
    discovery_config: DiscoveryConfig = Field(default_factory=DiscoveryConfig)
    capabilities: list[Capability] = Field(default_factory=list, description="能力列表")


class SmartEntityUpdate(BaseModel):
    """更新智能体请求"""
    name: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = None
    base_agent: Optional[Literal["build", "plan", "task"]] = None
    data_exchange_config: Optional[DataExchangeConfig] = None
    collaboration_config: Optional[CollaborationConfig] = None
    discovery_config: Optional[DiscoveryConfig] = None
    capabilities: Optional[list[Capability]] = None
    status: Optional[Literal["active", "inactive", "suspended"]] = None


class SmartEntityResponse(BaseModel):
    """智能体响应"""
    entity_id: str
    owner_user_id: int
    name: str
    description: str
    base_agent: str
    data_exchange_config: dict
    collaboration_config: dict
    discovery_config: dict
    capabilities: list[dict]
    status: str
    created_at: str
    updated_at: str


class SmartEntityListResponse(BaseModel):
    """智能体列表响应"""
    my_entities: list[SmartEntityResponse]
    discoverable_entities: list[SmartEntityResponse]


class SmartEntityTaskCreate(BaseModel):
    """创建智能体协作任务请求"""
    to_entity_id: str = Field(..., description="目标智能体ID")
    task_type: Literal["capability_request", "data_exchange", "review", "custom"] = Field(..., description="任务类型")
    task_title: str = Field(..., min_length=1, max_length=200, description="任务标题")
    task_description: str = Field(..., description="任务描述")
    input_data: Optional[dict] = Field(default=None, description="输入数据")
    required_capability: Optional[str] = Field(default=None, description="需要的能力（用于自动路由）")


class SmartEntityTaskResponse(BaseModel):
    """任务响应"""
    task_id: str
    from_entity_id: str
    from_user_id: int
    to_entity_id: str
    to_user_id: int
    task_type: str
    task_title: str
    task_description: str
    status: str
    attempt_count: int
    created_at: str
    expires_at: Optional[str] = None
    accepted_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class SmartEntityTaskAction(BaseModel):
    """任务操作请求"""
    action: Literal["accept", "reject", "cancel"]
    reason: Optional[str] = Field(default=None, description="操作原因")


class SmartEntityDiscoverRequest(BaseModel):
    """发现智能体请求"""
    capability: Optional[str] = Field(default=None, description="能力筛选")
    keywords: Optional[str] = Field(default=None, description="关键词搜索")
    require_auto_accept: Optional[bool] = Field(default=None, description="是否要求自动接受")


class SmartEntityDiscoverResponse(BaseModel):
    """发现智能体响应"""
    entity_id: str
    name: str
    owner: dict
    capabilities: list[dict]
    stats: dict
    match_score: float


class SmartEntityMetricResponse(BaseModel):
    """智能体指标响应"""
    entity_id: str
    total_tasks_received: int
    total_tasks_completed: int
    total_tasks_failed: int
    avg_response_time: int
    last_task_at: Optional[str] = None
    daily_quota: int
    daily_used: int
