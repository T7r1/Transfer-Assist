const btn = document.getElementById("btn");
const input = document.getElementById("collegeSelect2");
const ls = document.getElementById("myList");
myColleges = [];

//college search and add-er
btn.addEventListener("click", () => {
  const value = input.value.trim();
  if (value) {
    const li = document.createElement("li");
    li.textContent = value;
    ls.appendChild(li);

    //updates college list
    myColleges.push(value);
    input.value = "";
  } else {
    alert("Please enter a list item.");
  }
});

//reads university.json file
fetch("university.json")
  .then((response) => response.json()) // Automatically parses the JSON response
  .then((data) => {
    console.log(data);
    const selectElement = document.getElementById("collegeSelect");

    data.forEach((college) => {
      const newOption = document.createElement("option");
      newOption.textContent = college.name; // The text displayed to the user
      newOption.value = college.name; // The value submitted with the form
      selectElement.appendChild(newOption);
    });
  })
  .catch((error) => {
    console.error("Error fetching university data:", error);
  });
// const collegeCheckList = document.getElementById("collegeCheckList");
// for (let i = 0; i < array.length; i++) collegeCheckList.appendChild(college);
