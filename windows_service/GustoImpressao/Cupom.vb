Imports System.Text

Public Module CupomBuilder

    Private Const LARGURA As Integer = 42
    Private ReadOnly SEP_SIMPLES As String = New String("─"c, LARGURA)
    Private ReadOnly SEP_DUPLO As String = New String("═"c, LARGURA)

    Public Function MontarCupomIndividual(pedido As PedidoImpressao) As String
        Dim agora = DateTime.Now.ToString("dd/MM  HH:mm")
        Dim sb As New StringBuilder()

        sb.AppendLine(LinhaKV(agora, "INDIVIDUAL"))
        sb.AppendLine(SEP_SIMPLES)

        Dim fone = FormatarTelefone(pedido.NumeroWhatsapp)

        For Each item In pedido.Itens
            Dim nome = If(String.IsNullOrWhiteSpace(item.NomePessoa), "CLIENTE", item.NomePessoa).ToUpper()
            sb.AppendLine($"{nome}  {fone}")
            sb.AppendLine($"{item.Mistura}  {item.Tamanho}")

            Dim acomps = {item.Acomp1, item.Acomp2}.Where(Function(a) Not String.IsNullOrWhiteSpace(a)).ToArray()
            If acomps.Length > 0 Then
                sb.AppendLine(String.Join(" + ", acomps.Select(Function(a) ToTitleCase(a))))
            End If

            If Not String.IsNullOrWhiteSpace(item.Observacoes) Then
                sb.AppendLine($"⚠ {item.Observacoes}")
            End If
        Next

        If Not String.IsNullOrWhiteSpace(pedido.HoraRetirada) Then
            sb.AppendLine($"Retirada ~{pedido.HoraRetirada}")
        ElseIf Not String.IsNullOrWhiteSpace(pedido.EnderecoEntrega) Then
            sb.AppendLine($"Entrega: {pedido.EnderecoEntrega}")
        End If

        sb.AppendLine(SEP_SIMPLES)
        Return sb.ToString()
    End Function

    Public Function MontarCupomConvenio(pedido As PedidoImpressao, nomeEmpresa As String) As String
        Dim agora = DateTime.Now.ToString("dd/MM  HH:mm")
        Dim horaEnt = If(Not String.IsNullOrWhiteSpace(pedido.HoraRetirada), pedido.HoraRetirada, "—")

        Dim sb As New StringBuilder()
        sb.AppendLine(Centralizar($"★ {nomeEmpresa.ToUpper()} ★"))
        sb.AppendLine(Centralizar($"Entrega {horaEnt}"))
        sb.AppendLine(SEP_DUPLO)

        Dim totalValor As Decimal = 0
        For Each item In pedido.Itens
            Dim nome = If(String.IsNullOrWhiteSpace(item.NomePessoa), "", item.NomePessoa).ToUpper()
            Dim valorStr = If(item.ValorUnitario > 0, $"R${item.ValorUnitario:N2}".Replace(".", ","), "")

            sb.AppendLine(nome)
            Dim linhaPrato = $"  {item.Mistura}  {item.Tamanho}"
            sb.AppendLine(If(String.IsNullOrEmpty(valorStr), linhaPrato, LinhaKV(linhaPrato, valorStr)))

            Dim acomps = {item.Acomp1, item.Acomp2}.Where(Function(a) Not String.IsNullOrWhiteSpace(a)).ToArray()
            If acomps.Length > 0 Then
                sb.AppendLine("  " & String.Join(" + ", acomps.Select(Function(a) ToTitleCase(a))))
            End If

            If Not String.IsNullOrWhiteSpace(item.Observacoes) Then
                sb.AppendLine($"  ⚠ {item.Observacoes}")
            End If

            sb.AppendLine(SEP_SIMPLES)
            totalValor += item.ValorUnitario
        Next

        Dim totalStr = $"R${totalValor:N2}".Replace(".", ",")
        sb.AppendLine($"TOTAL: {pedido.Itens.Count} marmita(s)  {totalStr}")
        sb.AppendLine($"Forma pgto: {If(String.IsNullOrWhiteSpace(pedido.FormaPgto), "Convênio mensal", pedido.FormaPgto)}")
        sb.AppendLine(SEP_DUPLO)
        Return sb.ToString()
    End Function

    Private Function LinhaKV(chave As String, valor As String) As String
        Dim espacos = LARGURA - chave.Length - valor.Length
        If espacos < 1 Then espacos = 1
        Return chave & New String(" "c, espacos) & valor
    End Function

    Private Function Centralizar(texto As String) As String
        Return texto.PadLeft((LARGURA + texto.Length) \ 2).PadRight(LARGURA)
    End Function

    Private Function FormatarTelefone(numero As String) As String
        If String.IsNullOrEmpty(numero) Then Return ""
        If numero.StartsWith("55") AndAlso numero.Length >= 12 Then
            numero = numero.Substring(2)
        End If
        If numero.Length = 11 Then
            Return $"({numero.Substring(0, 2)}) {numero(2)}.{numero.Substring(3, 4)}-{numero.Substring(7)}"
        End If
        Return numero
    End Function

    Private Function ToTitleCase(s As String) As String
        If String.IsNullOrEmpty(s) Then Return s
        Return Char.ToUpper(s(0)) & s.Substring(1).ToLower()
    End Function

End Module
