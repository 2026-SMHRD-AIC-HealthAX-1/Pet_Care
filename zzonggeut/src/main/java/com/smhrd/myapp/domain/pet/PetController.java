package com.smhrd.myapp.domain.pet;

import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import java.util.List;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/pets")
public class PetController {
    private final PetService petService;

    @PostMapping
    public PetEntity createPet(@RequestParam String pName,
                               @RequestParam char pGender,
                               @RequestParam String pSpecies,
                               @RequestParam Byte pAge,
                               @RequestParam Integer pWeight,
                               @RequestParam String pSpec,
                               @RequestParam char isMule,
                               @RequestParam char isVaccin,
                               @RequestParam String pBeforeInfo) {
        return petService.savePet(pName, pGender, pSpecies, pAge, pWeight, pSpec, isMule, isVaccin, pBeforeInfo);
    }

    @GetMapping
    public List listPets() {
        return petService.getAllPets();
    }
}