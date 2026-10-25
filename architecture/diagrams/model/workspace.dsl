workspace "RetailPartnerX Knowledge Platform" "Curated C4 model with inventory-checked technical facts." {

    model {
        storeEmployee = person "Store Employee" "Asks product/policy questions."
        categoryManager = person "Category Manager" "ACL-scoped KB access."
        complianceOfficer = person "Compliance Officer" "Secret corpus access."
        platformOperator = person "Platform Operator" "Runs hybrid profiles."

        kp = softwareSystem "Knowledge Platform" "RetailPartnerX GraphRAG MVP." {
            frontend = container "Frontend" "React/Vite SPA" "TypeScript" "Chat, vision, ops."
            backend = container "Backend API" "FastAPI + LangGraph" "Python" "Guards, agent, stores." {
                apiRouter = component "API Router" "HTTP /v1/*" "FastAPI"
                chatService = component "ChatService" "Chat orchestration" "Python"
                visionService = component "VisionService" "OCR MOCK entry" "Python"
                inputGuard = component "Input Guard" "Injection checks" "Python"
                outputGuard = component "Output Guard" "ACL leak checks" "Python"
                rbac = component "RBAC" "can_access" "Python"
                agent = component "KnowledgeAgent" "LangGraph state machine" "LangGraph"
                hybridStore = component "HybridKnowledgeStore" "Store facade" "Python"
                llmClient = component "LLMClient" "MOCK/OLLAMA/VLLM" "Python"
                objectStore = component "ObjectStore" "FS or MinIO" "Python"
                audit = component "Audit" "In-memory audit" "Python"
            }
            neo4j = container "Neo4j" "Graph store" "Neo4j 5" "Product graph."
            qdrant = container "Qdrant" "Vector index" "Qdrant" "Dense + ACL."
            redis = container "Redis" "Cache" "Redis" "Optional semantic cache."
            minio = container "MinIO" "Object store" "MinIO" "Label assets."
            postgres = container "Postgres" "Metadata DB" "PostgreSQL 16" "Deployed-unused."
        }

        ollama = softwareSystem "Ollama host" "Compose profile llm." {
            tags "External,HostSide"
        }
        obsStack = softwareSystem "Observability side-stack" "Tempo Loki Grafana on host." {
            tags "External,HostSide"
        }
        corporateIdp = softwareSystem "Corporate IdP" "Future OIDC." {
            tags "Target"
        }
        vault = softwareSystem "HashiCorp Vault" "Future secrets." {
            tags "Target"
        }
        vllmHost = softwareSystem "vLLM GPU host" "Submission profile." {
            tags "Target,HostSide"
        }
        realOcr = softwareSystem "Vision OCR Engine" "Out of MVP." {
            tags "Target"
        }

        storeEmployee -> frontend "Uses UI"
        categoryManager -> frontend "Uses UI"
        complianceOfficer -> frontend "Uses UI"
        platformOperator -> frontend "Ops pages"
        platformOperator -> obsStack "Dashboards"

        frontend -> backend "HTTPS /api"
        backend -> neo4j "Bolt live"
        backend -> qdrant "HTTP live"
        backend -> redis "Cache optional"
        backend -> minio "S3 live"
        backend -> ollama "OpenAI-compatible"
        backend -> obsStack "OTLP"

        apiRouter -> chatService "delegates"
        apiRouter -> visionService "delegates"
        chatService -> inputGuard "check"
        chatService -> agent "arun"
        chatService -> outputGuard "via agent"
        chatService -> audit "record"
        agent -> hybridStore "retrieve"
        agent -> llmClient "complete"
        agent -> inputGuard "node"
        agent -> outputGuard "node"
        agent -> rbac "Principal ACL"
        visionService -> objectStore "store asset"
        visionService -> hybridStore "index extract"
        hybridStore -> neo4j "graph_resolve"
        hybridStore -> qdrant "hybrid_retrieve"

        kp -> corporateIdp "Authenticate planned" {
            tags "Target"
        }
        kp -> vault "Secrets planned" {
            tags "Target"
        }
        backend -> vllmHost "Submission LLM" {
            tags "Target"
        }
        backend -> realOcr "OCR planned" {
            tags "Target"
        }

        live = deploymentEnvironment "Desktop Hybrid" {
            deploymentNode "Developer Workstation" "" "Docker Desktop" {
                deploymentNode "Kubernetes" "" "namespace kp" {
                    containerInstance frontend
                    containerInstance backend
                    deploymentNode "Data Plane" "" "Helm" {
                        containerInstance neo4j
                        containerInstance qdrant
                        containerInstance redis
                        containerInstance minio
                        containerInstance postgres
                    }
                }
                deploymentNode "Compose Side-Stack" "" "host" {
                    softwareSystemInstance ollama
                    softwareSystemInstance obsStack
                }
            }
        }
    }

    views {
        systemContext kp "current-context" {
            include *
            exclude element.tag==Target
            exclude relationship.tag==Target
            autoLayout
            description "L1 Context current."
        }

        container kp "current-containers" {
            include *
            exclude element.tag==Target
            exclude relationship.tag==Target
            autoLayout
            description "L2 Containers current."
        }

        component backend "current-backend-components" {
            include *
            autoLayout
            description "L3 Backend components."
        }

        deployment kp live "current-hybrid-deployment" {
            include *
            autoLayout
            description "Hybrid deployment; GPU pending."
        }

        systemLandscape "target-overview" {
            include *
            autoLayout
            description "Target overview with planned systems."
        }

        styles {
            element "Person" {
                shape person
                background #08427B
                color #ffffff
            }
            element "Software System" {
                background #1168BD
                color #ffffff
            }
            element "Container" {
                background #438DD5
                color #ffffff
            }
            element "Component" {
                background #85BBF0
                color #000000
            }
            element "External" {
                background #999999
                color #ffffff
            }
            element "HostSide" {
                background #666666
                color #ffffff
            }
            element "Target" {
                background #EEEEEE
                color #333333
                border dashed
            }
            relationship "Target" {
                color #888888
                style dashed
            }
        }
    }

}
