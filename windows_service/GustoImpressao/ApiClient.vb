Imports System.Net.Http
Imports System.Text.Json
Imports Microsoft.Extensions.Logging
Imports Microsoft.Extensions.Options

Public Class ApiClient
    Private ReadOnly _http As HttpClient
    Private ReadOnly _cfg As GustoConfig
    Private ReadOnly _log As ILogger(Of ApiClient)

    Public Sub New(httpFactory As IHttpClientFactory, cfg As IOptions(Of GustoConfig), log As ILogger(Of ApiClient))
        _cfg = cfg.Value
        _log = log
        _http = httpFactory.CreateClient()
        _http.BaseAddress = New Uri(_cfg.ApiUrl.TrimEnd("/"c) & "/")
        _http.DefaultRequestHeaders.Add("X-Api-Key", _cfg.ApiKey)
        _http.Timeout = TimeSpan.FromSeconds(15)
    End Sub

    Public Async Function BuscarPendentes() As Task(Of List(Of PedidoImpressao))
        Dim resp = Await _http.GetAsync("api/impressao/pendentes")
        resp.EnsureSuccessStatusCode()

        Dim json = Await resp.Content.ReadAsStringAsync()
        Dim doc = JsonDocument.Parse(json)

        Dim lista As New List(Of PedidoImpressao)
        Dim pedidosEl As JsonElement
        If Not doc.RootElement.TryGetProperty("pedidos", pedidosEl) Then Return lista

        For Each entry In pedidosEl.EnumerateArray()
            Dim p As New PedidoImpressao()

            Dim pedidoEl As JsonElement
            If entry.TryGetProperty("pedido", pedidoEl) Then
                p.Id = GetInt(pedidoEl, "id")
                p.Tipo = GetStr(pedidoEl, "tipo")
                p.NumeroWhatsapp = GetStr(pedidoEl, "numero_whatsapp")
                p.EnderecoEntrega = GetStr(pedidoEl, "endereco_entrega")
                p.HoraRetirada = GetStr(pedidoEl, "hora_retirada")
                p.EmpresaId = GetInt(pedidoEl, "empresa_id")
                p.NomeEmpresa = GetStr(pedidoEl, "nome_empresa")
                p.FormaPgto = GetStr(pedidoEl, "forma_pgto")
            End If

            Dim itensEl As JsonElement
            If entry.TryGetProperty("itens", itensEl) Then
                For Each itemEl In itensEl.EnumerateArray()
                    p.Itens.Add(New ItemImpressao With {
                        .NomePessoa = GetStr(itemEl, "nome_pessoa"),
                        .Mistura = GetStr(itemEl, "mistura"),
                        .Tamanho = GetStr(itemEl, "tamanho"),
                        .Acomp1 = GetStr(itemEl, "acomp_1"),
                        .Acomp2 = GetStr(itemEl, "acomp_2"),
                        .Observacoes = GetStr(itemEl, "observacoes"),
                        .ValorUnitario = GetDec(itemEl, "valor_unitario")
                    })
                Next
            End If

            lista.Add(p)
        Next
        Return lista
    End Function

    Public Async Function MarcarImpresso(pedidoId As Integer) As Task
        Dim resp = Await _http.PostAsync($"api/impressao/{pedidoId}/marcar", Nothing)
        resp.EnsureSuccessStatusCode()
    End Function

    Private Shared Function GetStr(el As JsonElement, prop As String) As String
        Dim v As JsonElement
        If el.TryGetProperty(prop, v) AndAlso v.ValueKind = JsonValueKind.String Then Return v.GetString() Else Return ""
    End Function

    Private Shared Function GetInt(el As JsonElement, prop As String) As Integer
        Dim v As JsonElement
        If el.TryGetProperty(prop, v) AndAlso v.ValueKind = JsonValueKind.Number Then Return v.GetInt32() Else Return 0
    End Function

    Private Shared Function GetDec(el As JsonElement, prop As String) As Decimal
        Dim v As JsonElement
        If el.TryGetProperty(prop, v) AndAlso v.ValueKind = JsonValueKind.Number Then Return v.GetDecimal() Else Return 0D
    End Function
End Class

Public Class PedidoImpressao
    Public Property Id As Integer
    Public Property Tipo As String = "individual"
    Public Property NumeroWhatsapp As String = ""
    Public Property EnderecoEntrega As String = ""
    Public Property HoraRetirada As String = ""
    Public Property EmpresaId As Integer
    Public Property NomeEmpresa As String = ""
    Public Property FormaPgto As String = ""
    Public Property Itens As New List(Of ItemImpressao)
End Class

Public Class ItemImpressao
    Public Property NomePessoa As String = ""
    Public Property Mistura As String = ""
    Public Property Tamanho As String = ""
    Public Property Acomp1 As String = ""
    Public Property Acomp2 As String = ""
    Public Property Observacoes As String = ""
    Public Property ValorUnitario As Decimal
End Class
