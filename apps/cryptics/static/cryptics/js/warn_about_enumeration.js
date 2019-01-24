function check_for_enumeration(s){
    var warning_element = document.getElementById("enum_warning")
    var new_sub_element = document.getElementById("new_submission")
    var ENUM_REGEX = /\([^A-Za-z]*\d+[^A-Za-z]*\)\s*$/
    if (ENUM_REGEX.test(new_sub_element.value)){
        console.log("Passed regex!")
        warning_element.style.display = "none"
    } else {
        console.log("Failed regex!")
        warning_element.style.display = "block"
    }
}

document.getElementById("new_submission").addEventListener("focusout", check_for_enumeration)
