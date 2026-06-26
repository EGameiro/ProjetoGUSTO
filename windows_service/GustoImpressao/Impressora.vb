Imports System.Drawing
Imports System.Drawing.Printing
Imports System.Drawing.Text
Imports Microsoft.Extensions.Logging

Public Class Impressora
    Private ReadOnly _nomeImpressora As String
    Private ReadOnly _log As ILogger

    Public Sub New(nomeImpressora As String, log As ILogger)
        _nomeImpressora = nomeImpressora
        _log = log
    End Sub

    Public Sub Imprimir(cupom As String)
        Try
            Dim doc As New PrintDocument()

            If Not String.IsNullOrWhiteSpace(_nomeImpressora) Then
                doc.PrinterSettings.PrinterName = _nomeImpressora
                If Not doc.PrinterSettings.IsValid Then
                    _log.LogWarning("Impressora '{Nome}' não encontrada. Usando impressora padrão.", _nomeImpressora)
                    doc.PrinterSettings.PrinterName = Nothing
                End If
            End If

            Dim linhas = cupom.Split({vbCrLf, vbLf}, StringSplitOptions.None)
            Dim indice As Integer = 0

            AddHandler doc.PrintPage, Sub(sender, e)
                Dim fonte As New Font("Courier New", 9, FontStyle.Regular, GraphicsUnit.Point)
                Dim y As Single = e.MarginBounds.Top
                Dim alturaLinha = fonte.GetHeight(e.Graphics)

                While indice < linhas.Length
                    Dim linha = linhas(indice)
                    e.Graphics.DrawString(linha, fonte, Brushes.Black, e.MarginBounds.Left, y)
                    y += alturaLinha
                    indice += 1

                    If y + alturaLinha > e.MarginBounds.Bottom Then
                        e.HasMorePages = True
                        Exit Sub
                    End If
                End While

                fonte.Dispose()
                e.HasMorePages = False
            End Sub

            doc.Print()
            _log.LogInformation("Cupom enviado para impressão.")

        Catch ex As Exception
            _log.LogError(ex, "Erro ao imprimir cupom.")
        End Try
    End Sub
End Class
