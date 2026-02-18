# Trabalhando Aplicacoes Serverless na Azure

## Projeto DIO - Microsoft Azure Advanced #2

Este repositorio documenta o projeto pratico sobre aplicacoes serverless na Azure, explorando Azure Functions, Logic Apps e Service Bus.

## Objetivo

Explorar as diferencas funcionais entre Azure Functions, Logic Apps e WebJobs, descrever as opcoes de plano de hospedagem do Azure Functions e entender como o Azure Functions escala para atender as necessidades dos negocios.

## Tecnologias Utilizadas

- **Azure Functions** - Servico de computacao serverless para executar codigo sob demanda
- **Azure Logic Apps** - Plataforma de integracao para automatizar workflows
- **Azure Service Bus** - Servico de mensageria corporativa
- **Azure WebJobs** - Execucao de tarefas em background

## Comparacao: Azure Functions vs Logic Apps vs WebJobs

| Caracteristica | Azure Functions | Logic Apps | WebJobs |
|---|---|---|---|
| Modelo | Serverless | Serverless | App Service |
| Trigger | HTTP, Timer, Queue, Blob | 200+ conectores | Timer, Queue, Blob |
| Linguagens | C#, JS, Python, Java, PowerShell | Designer visual | C#, Script |
| Escalabilidade | Auto-scale | Auto-scale | Manual/Auto |
| Custo | Pay-per-execution | Pay-per-execution | App Service Plan |

## Planos de Hospedagem do Azure Functions

### 1. Consumption Plan (Plano de Consumo)
- Escala automaticamente
- Pagamento apenas por execucao
- Timeout padrao de 5 minutos (max 10)
- Cold start possivel

### 2. Premium Plan
- Instancias pre-aquecidas (sem cold start)
- Conectividade VNet
- Execucao ilimitada
- Hardware mais poderoso

### 3. Dedicated (App Service) Plan
- Executa em VMs dedicadas
- Ideal para cenarios long-running
- Escala manual ou auto-scale
- Custo previsivel

## Arquitetura do Projeto

```
[Event Source] --> [Azure Functions] --> [Service Bus Queue] --> [Logic App]
     |                    |                                        |
     v                    v                                        v
 [HTTP Request]    [Process Data]                          [Send Notification]
 [Timer]           [Transform]                             [Update Database]
 [Queue Message]   [Validate]                              [Call External API]
```

## Exemplo: Azure Function com HTTP Trigger

```csharp
[FunctionName("ProcessOrder")]
public static async Task<IActionResult> Run(
    [HttpTrigger(AuthorizationLevel.Function, "post")] HttpRequest req,
    [ServiceBus("orders-queue")] IAsyncCollector<string> outputMessages,
    ILogger log)
{
    string requestBody = await new StreamReader(req.Body).ReadToEndAsync();
    var order = JsonConvert.DeserializeObject<Order>(requestBody);
    log.LogInformation($"Processing order: {order.Id}");
    await outputMessages.AddAsync(JsonConvert.SerializeObject(order));
    return new OkObjectResult(new { message = "Order processed", orderId = order.Id });
}
```

## Exemplo: Azure Function com Service Bus Trigger

```csharp
[FunctionName("ProcessQueueMessage")]
public static void Run(
    [ServiceBusTrigger("orders-queue")] string message,
    ILogger log)
{
    var order = JsonConvert.DeserializeObject<Order>(message);
    log.LogInformation($"Processing queued order: {order.Id}");
}
```

## Recursos e Links Importantes

- [Azure Functions Documentation](https://learn.microsoft.com/azure/azure-functions/)
- [Azure Logic Apps Documentation](https://learn.microsoft.com/azure/logic-apps/)
- [Azure Service Bus Documentation](https://learn.microsoft.com/azure/service-bus-messaging/)
- [Serverless Computing](https://azure.microsoft.com/solutions/serverless/)

## Autor

Projeto desenvolvido como parte do bootcamp **Microsoft Azure Advanced #2** da [DIO](https://www.dio.me/).
