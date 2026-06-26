Imports Microsoft.Extensions.DependencyInjection
Imports Microsoft.Extensions.Hosting

Module Program
    Sub Main(args As String())
        Dim builder = Host.CreateDefaultBuilder(args)
        builder.UseWindowsService(Sub(o) o.ServiceName = "GustoImpressao")
        builder.ConfigureServices(Sub(ctx, services)
            services.Configure(Of GustoConfig)(ctx.Configuration.GetSection("Gusto"))
            services.AddHttpClient()
            services.AddHostedService(Of PollerWorker)()
        End Sub)
        builder.Build().Run()
    End Sub
End Module
