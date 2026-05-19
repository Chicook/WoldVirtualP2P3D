# Investigación del Bug: "Error al guardar registro: El índice está fuera del límite de la colección"

## Descripción del Problema
En la imagen proporcionada, el visor de WPF (Capa3_Visor) lanza un error crítico al intentar finalizar el registro o iniciar sesión. El mensaje rojo en la parte inferior izquierda indica:

`Error al guardar registro: Specified argument was out of the range of valid values. (Parameter 'El índice está fuera del límite de la colección.')`

A primera vista, el texto "Error al guardar registro" sugiere un fallo en la inserción o actualización de la base de datos local (SQLite). Sin embargo, el mensaje de la excepción subyacente *"El índice está fuera del límite de la colección"* (la traducción en español estándar de .NET para `IndexOutOfRangeException` / `ArgumentOutOfRangeException`) revela que el error se produce al intentar acceder a un índice inexistente en un Array o Colección en C#.

## Análisis de Código
El bloque de código que lanza el texto "Error al guardar registro: " se encuentra en el método `BtnFinalizeRegister_Click` en el archivo `MainWindow.xaml.cs`:

```csharp
try
{
    // 1. Guardar en BD local
    _db.RegisterUser(_username, TxtRegPass.Password.Trim(), _fingerprint.UniqueHash, _islandId);
    _db.UpdateWallet(_username, _wallet);
    
    // 2. Iniciar Dashboard
    EnterDashboard(isNewRegistration: true);
}
catch (Exception ex)
{
    TxtFooterStatus.Text = $"Error al guardar registro: {ex.Message}";
    TxtFooterStatus.Foreground = new SolidColorBrush(Colors.Red);
}
```

La excepción es capturada aquí, pero **no se origina en las llamadas a la base de datos**. Al revisar el método `EnterDashboard()`, que gestiona la transición de la UI y lanza el Godot Viewer, encontramos lo siguiente:

```csharp
// Líneas 490-497 aprox. en EnterDashboard():
LogDebug($"PanViewportContainer dimensions: ActualWidth={PanViewportContainer.ActualWidth}, ActualHeight={PanViewportContainer.ActualHeight}");
LogDebug($"GodotPlaceholder dimensions: ActualWidth={GodotPlaceholder.ActualWidth}, ActualHeight={GodotPlaceholder.ActualHeight}");
LogDebug($"Main Grid column 1 width: {((Grid)PanViewportContainer.Parent).ColumnDefinitions[1].Width}");
```

## Causa Raíz (Root Cause)
La variable `PanViewportContainer` (el contenedor de Godot) se encuentra dentro de un `<Grid Grid.Column="1">` secundario en el XAML. Este Grid secundario se usa únicamente para agrupar los Wizards y el visor 3D en la misma columna de la ventana principal.

Este `Grid` padre inmediato **no tiene columnas definidas explícitamente** (`ColumnDefinitions.Count == 0`). 

Por lo tanto, cuando el método `LogDebug` intenta acceder a `.ColumnDefinitions[1]` de ese Grid secundario, WPF lanza una `ArgumentOutOfRangeException` (cuyo mensaje en español es *"El índice está fuera del límite de la colección"*).

Dado que esta línea de Log se ejecuta inmediatamente antes de lanzar el Metaverso, la excepción interrumpe la transición de la UI. La excepción "sube" por el stack y es capturada por el `try/catch` del botón de Finalizar, que engañosamente le adjunta el prefijo *"Error al guardar registro:"*.

## Solución Aplicada
La solución es eliminar o corregir la línea de código defectuosa, ya que solo era un registro de consola (`LogDebug`) que asumía de forma incorrecta la jerarquía visual del contenedor.

Se ha modificado el archivo `MainWindow.xaml.cs`, eliminando la siguiente línea en `EnterDashboard`:

```csharp
// ELIMINADO:
// LogDebug($"Main Grid column 1 width: {((Grid)PanViewportContainer.Parent).ColumnDefinitions[1].Width}");
```

Con este cambio mínimo, la transición de la UI se completa de forma limpia y Godot 3D se embebe correctamente en el visualizador sin arrojar el error de índices.
