package com.smhrd.myapp.domain.pet;

import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;

@Controller
@RequiredArgsConstructor
public class PetController {

    private final PetService petService;

    @GetMapping("/pet/register")
    public String petRegisterPage() {
        return "petRegister"; // templates/petRegister.html
    }

    @PostMapping("/pet/register")
    public String registerPet(@RequestParam Long userId,
                              @RequestParam String name,
                              @RequestParam String species,
                              @RequestParam Integer age) {
        petService.register(userId, name, species, age);
        return "redirect:/main";
    }
}