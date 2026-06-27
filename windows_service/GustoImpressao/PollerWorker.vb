Imports System.Net.Http
Imports System.Threading
Imports Microsoft.Extensions.Hosting
Imports Microsoft.Extensions.Logging
Imports Microsoft.Extensions.Options
Imports Microsoft.Extensions.DependencyInjection

Public Class PollerWorker
    Inherits BackgroundService

    Private ReadOnly _log As ILogger(Of PollerWorker)
    Private ReadOnly _cfg As GustoConfig
    Private ReadOnly _api As ApiClient
    Private ReadOnly _impressora As Impressora

    Public Sub New(log As ILogger(Of PollerWorker),
                   cfg As IOptions(Of GustoConfig),
                   httpFactory As IHttpClientFactory,
                   apiLog As ILogger(Of ApiClient))
        _log = log
        _cfg = cfg.Value
        _api = New ApiClient(httpFactory, cfg, apiLog)
        _impressora = New Impressora(_cfg.NomeImpressora, log)
    End Sub

    Protected Overrides Async Function ExecuteAsync(ct As CancellationToken) As Task
        _log.LogInformation("GUSTO Impressão iniciado. Intervalo={Seg}s | Impressora={Imp}",
                            _cfg.IntervaloSegundos,
                            If(String.IsNullOrWhiteSpace(_cfg.NomeImpressora), "(padrão)", _cfg.NomeImpressora))

        While Not ct.IsCancellationRequested
            Await ProcessarPendentes()
            Await Task.Delay(TimeSpan.FromSeconds(_cfg.IntervaloSegundos), ct)
        End While
    End Function

    Private Async Function ProcessarPendentes() As Task
        Dim pendentes As List(Of PedidoImpressao)
        Try
            pendentes = Await _api.BuscarPendentes()
        Catch ex As Exception
            _log.LogError(ex, "Erro ao buscar pedidos pendentes.")
            Return
        End Try

        For Each pedido In pendentes
            Try
                _log.LogInformation("Imprimindo pedido #{Id} (tipo={Tipo})", pedido.Id, pedido.Tipo)

                Dim cupom As String
                If pedido.Tipo = "convenio" Then
                    Dim nomeEmp = If(String.IsNullOrWhiteSpace(pedido.NomeEmpresa), "EMPRESA", pedido.NomeEmpresa)
                    cupom = CupomBuilder.MontarCupomConvenio(pedido, nomeEmp)
                Else
                    cupom = CupomBuilder.MontarCupomIndividual(pedido)
                End If

                _impressora.Imprimir(cupom)
                Await _api.MarcarImpresso(pedido.Id)
                _log.LogInformation("Pedido #{Id} marcado como impresso.", pedido.Id)

            Catch ex As Exception
                _log.LogError(ex, "Erro ao processar pedido #{Id}.", pedido.Id)
            End Try
        Next
    End Function
End Class
