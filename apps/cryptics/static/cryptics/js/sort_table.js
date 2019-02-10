// Modified from https://stackoverflow.com/a/49041392

function get_cell_value(tr, idx){
    // Get the text of a cell
    return tr.children[idx].innerText || tr.children[idx].textContent
}

function compare_values(a, b){
    // compare two values
    // if either value isn't numeric, compare as case-insensitive strings
    // otherwise compare as floats
    if(isNaN(a) || isNaN(b)) {
        a = a.toUpperCase()
        b = b.toUpperCase()
    } else {
        a = parseFloat(a)
        b = parseFloat(b)
    }

    if(a < b){
        return -1
    } else if (a > b){
        return 1
    } else {
        return 0
    }
}

function sort_by_col(e) {
    var this_th = e.currentTarget
    var table = this_th.closest("table")
    var idx = Array.from(this_th.parentNode.children).indexOf(this_th)
    var rows = Array.from(table.querySelectorAll("tr:nth-child(n+2)"))
    rows.sort((tr1, tr2) => compare_values(get_cell_value(tr1, idx), get_cell_value(tr2, idx)))

    if(this_th.asc){
        rows.reverse()
    }

    this_th.asc = !this_th.asc

    rows.forEach(tr => table.appendChild(tr))

    document.querySelectorAll(".sort_column").forEach(el => el.classList.remove("sort_column"))
    this_th.classList.add("sort_column")
}

document.querySelectorAll("th").forEach(th => th.addEventListener("click", sort_by_col))
