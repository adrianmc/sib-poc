# C07-AE-06: diagrama de red y seguridad del ambiente de demo

```mermaid
flowchart TB
  subgraph Internet
    SBU[Usuarios SIB / Power BI / Claude Desktop]
    CP[Cloudera Control Plane - SaaS]
    ENTRA[Entra ID - SAML/SCIM/MFA]
  end
  subgraph AWS["Cuenta AWS PoC - region us-east-2 (Ohio)"]
    subgraph VPC["VPC 10.10.0.0/16"]
      subgraph PUB["Subnets publicas x3 AZ"]
        NAT[NAT Gateways]
        LB[Load balancers CDW y Cloudera AI - allowlist de IP]
      end
      subgraph PRIV["Subnets privadas /19 x3 AZ"]
        DL[Data Lake: Ranger, Atlas, HMS, Knox, IDBroker, FreeIPA]
        DH[Data Hub sibrd-kafka: Kafka + Kafka Connect con Debezium]
        EKS[EKS: CDW VW impala-sib-a e impala-sib-waa, Cloudera AI: sesiones, jobs, modelos, AI Registry]
        GW[EC2 Windows 10.10.2.235: SQL Server 2022 base sbcore, Power BI Desktop, runner GitHub]
      end
    end
    S3[(S3 lakehouse SSE-KMS)]
    AUD[(S3 auditoria - Object Lock WORM)]
    KMS[AWS KMS CMK - opcional CipherTrust CCKM]
    CT[CloudTrail]
  end
  SBU -->|TLS 443| LB
  ENTRA -->|SAML| CP
  CP <-->|CCMv2 saliente TLS| DL
  EKS --> S3
  DL -->|RAZ: Ranger autoriza cada acceso a S3| S3
  DL -->|Ranger audit| AUD
  KMS --> S3
  DH -->|Debezium lee CDC por 1433| GW
```

Controles a narrar: identidad unica (Entra -> CDP -> FreeIPA -> Ranger), sin credenciales AWS de larga duracion para usuarios
(IDBroker mapea identidad a rol IAM), cifrado en reposo con CMK y en transito con TLS, endpoints publicos restringidos por IP
(o privados con VPN/Direct Connect en produccion), auditoria inmutable, separacion por tenant (VW/VC/workspace).
Produccion objetivo: un ambiente CDP por dev/test/prod, cada uno con su VPC o subnets, Data Lake, rol IAM y buckets.
