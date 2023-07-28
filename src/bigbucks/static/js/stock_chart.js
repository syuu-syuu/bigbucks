const inputElement = document.getElementById("stock-symbol");
const submitButton = document.getElementById("submit");

submitButton.disabled = true;

inputElement.addEventListener("input", () => {
    submitButton.disabled = inputElement.value.trim() === "";
});

submitButton.addEventListener("click", submitForm)
function submitForm() {
    const stockSymbol = inputElement.value.trim().toUpperCase();
    const startDate = document.getElementById("start-date").value;
    const endDate = document.getElementById("end-date").value;

    bootbox.confirm({
        message: 'Do you want to open the stock data of ' + stockSymbol + "?",
        buttons: {
            confirm: {
                label: 'Yes',
                className: 'btn-success'
            },
            cancel: {
                label: 'No',
                className: 'btn-danger'
            }
        },
        callback: function (result) {
            if (result) {
                console.log('Form Submitted');
                makeplot(stockSymbol, startDate, endDate);
                showlist(stockSymbol, startDate, endDate);
            } else {
                console.log('Action Cancelled');
            }
        }
    });
}

function showlist(stockSymbol, startDate, endDate) {
    console.log("showlist: start")
    const formattedStartDate = new Date(startDate).toISOString().split('T')[0];
    const formattedEndDate = new Date(endDate).toISOString().split('T')[0];
    fetch(`/api/stock_data?stock_symbol=${stockSymbol}&start_date=${formattedStartDate}&end_date=${formattedEndDate}`)
        .then((response) => response.text())
        .catch((error) => {
            alert(error)
        })
        .then((text) => {

            console.log(text)
            tableTitle = document.getElementById("tableTitle")
            myTable = document.getElementById("myTable")
            var lines = text.split("\n"),
                output = [],
                i;
            output.push("<tr><th>"
                + lines[0].slice().split(",").join("</th><th>")
                + "</th></tr>");

            for (i = 1; i < lines.length; i++)
                output.push("<tr><td>"
                    + lines[i].slice().split(",").join("</td><td>")
                    + "</td></tr>");

            output = "<table><tbody>"
                + output.join("") + "</tbody></table>";

            tableTitle.innerHTML = stockSymbol + " Stock Price History Data:"
            myTable.innerHTML = output;


        })


};


function makeplot(stockSymbol, startDate, endDate) {
    console.log("makeplot: start")
    const formattedStartDate = new Date(startDate).toISOString().split('T')[0];
    const formattedEndDate = new Date(endDate).toISOString().split('T')[0];
    fetch(`/api/stock_data?stock_symbol=${stockSymbol}&start_date=${formattedStartDate}&end_date=${formattedEndDate}`)
        .then((response) => response.text())
        .catch((error) => {
            alert(error)
        })
        .then((text) => {
            console.log("csv: start")
            csv().fromString(text)
                .then((csvData) => {
                    processData(csvData)
                })
            console.log("csv: end")
        })
    console.log("makeplot: end")

};

function processData(data) {
    console.log("processData: start")
    let x = [], y = []
    for (let i = 0; i < data.length; i++) {
        row = data[i]
        x.push(row['Date']);
        y.push(row['Close']);
    }
    makePlotly(x, y);
    console.log("processData: end")
};

function makePlotly(x, y) {
    console.log("makePlotly: start")
    var traces = [{
        x: x,
        y: y
    }];
    var layout = { title: stockSymbol + " Stock Price History" }
    myDiv = document.getElementById('myDiv');
    Plotly.newPlot(myDiv, traces, layout);
    console.log("makePlotly: end")
};


