# Striptool

Striptool plots channel access and pvAccess scalar variables.

By default striptool plots channel access PVs.  PVs can be specified from command-line, configuration file, or from the GUI.

## Quickstart
```bash
> c2dv --app striptool --pv <comma-separated PV list>
```

## Zooming
To zoom, scroll using the scroll wheel or trackpad.  To pan, left click and drag.  To see all mouse interactions, see [pyqtgraph's documentation](https://pyqtgraph.readthedocs.io/en/latest/mouse_interaction.html).

You can also configure the X/Y range, by right-clicking on the plot, select options from either the X-axis or Y-axis menus.

## Exporting data

Plotted data can be exported to a file by right-clicking on the plot, then select the "export" from the menu.  For more information, see [pyqtgraph's documentation](https://pyqtgraph.readthedocs.io/en/latest/user_guide/exporting.html)

## Configuration
PVs can be specified by a configuration file. Below is an example:
```ini
[DEFAULT]
APP=STRIPTOOL

[STRIPTOOL]
SECTION=DISPLAY
DefaultProtocol = ca
Chan1.PV = S:R:reg1
Chan2.PV = S:R:reg2
Chan3.PV = S:R:reg3

[DISPLAY]
Autoscale=true
```
Striptool configurations must start with:

```ini
[DEFAULT]
APP=STRIPTOOL

[STRIPTOOL]
```
Under `STRIPTOOL`, you can optionally add a `SECTION` field to add additional sections, which lists additional sections in the file. Below are configuration settings specific to the striptool app for each section. Note that fields and values are case insensitive.

### ACQUISITION
| Setting | Description
|---|---|
| Buffer | Buffer size (number of samples). Default varies by application |
| SampleMode | Enable sample mode. Set to true or false. Default is true |

### DISPLAY
| Setting | Description |
|---|---|
| Refresh | Refresh time in milliseconds. Default is 100 ms |
| Autoscale | Enable autoscale. Set to true or false. Default is true for Striptool. |
| Mode | Set display mode. Valid values are: "normal", "fft", "psd", "diff", "autocorrelate_fft". Default is "normal" |
| FFT\_FILTER | FFT filter to apply. Valid values are: "none", "hamming". Default is "none" |
| Average | Exponential moving average (EMA) value. Must be >= 1. Default is 1 |
| Single\_Axis | Enable single axis mode. Set to true or false. Default is true |
| Histogram | Turns on histogram mode. Set to true or false. Default is false |
| N\_BIN | Number of bins for histogram. Default is 100 |

### STRIPTOOL
| Setting | Description
|---|---|
| Section | List of additional sections to read in the config file |
| DefaultProtocol | Default PV protocol. Valid values: 'ca' and 'pva'. Default is 'ca'. Used if protocol is not specified for each PV |
| Chan[ID].PV | PV channel name. Can specify the protocol by starting name with [proto]://pvname, where [proto] is either 'ca' or 'pva'. Otherwise, uses the default protocol. Protocol prefix is case-insensitive. Examples: `Chan1.PV = ca://S:R:reg1`, `Chan2.PV = pva://S:R:reg2`, `Chan3.PV = S:R:reg3` |
| Chan[ID].Color | Color to plot for "Chan[ID]" in hex format. If not set, striptool will automatically assign a color from the default palette. Example: `Chan1.Color = #00FF00` |





